"""
CADLens – Unified FastAPI backend
Combines annotation detection (CV/OCR/YOLO) + full REST API + MongoDB persistence.
"""

import os
import re
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import pytesseract
from bson import ObjectId
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import pymupdf as fitz  # P2 fix: 'fitz' API deprecated
from PIL import Image
from pydantic import BaseModel

from database import balloons_collection, documents_collection
from balloon_manager import assign_balloon_numbers, spread_overlapping_balloons
from detector import detect_annotations, detect_from_pdf_page  # P10 fix: native PDF path
from exporter import export_to_excel
from models import BalloonCreate, BalloonUpdate

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cadlens")
logging.getLogger("ultralytics").setLevel(logging.WARNING)

# ── YOLO (optional) ───────────────────────────────────────────────────────────
try:
    from ultralytics import YOLO

    _yolo_path = Path(__file__).parent / "balloon_detector.pt"
    if _yolo_path.exists():
        yolo_model = YOLO(str(_yolo_path))
        USE_YOLO = True
        logger.info("Loaded YOLO balloon detector.")
    else:
        yolo_model = None
        USE_YOLO = False
        logger.info("balloon_detector.pt not found — falling back to OpenCV.")
except ImportError:
    yolo_model = None
    USE_YOLO = False
    logger.info("ultralytics not installed — falling back to OpenCV.")

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "storage" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

EXPORT_DIR = BASE_DIR / "storage" / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="CADLens API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _oid(oid) -> str:
    return str(oid)


def _serialize_doc(doc: dict) -> dict:
    """Convert ObjectId fields to strings for JSON serialisation."""
    doc["id"] = _oid(doc.pop("_id"))
    return doc


def _serialize_balloon(b: dict) -> dict:
    b["id"] = _oid(b.pop("_id"))
    if not b.get("units"):
        b_type = b.get("type", "")
        b_text = str(b.get("text", ""))
        if b_type == "Dimension":
            b["units"] = "°" if "°" in b_text else "mm"
        elif b_type == "Surface Finish":
            b["units"] = "µm"
        elif b_type == "Tolerance":
            b["units"] = "°" if "°" in b_text else "mm"
        elif b_type == "GD&T":
            b["units"] = "mm"
        else:
            b["units"] = ""
    return b


def compute_iou(box1, box2):
    x_left = max(box1[0], box2[0])
    y_top = max(box1[1], box2[1])
    x_right = min(box1[2], box2[2])
    y_bottom = min(box1[3], box2[3])
    if x_right < x_left or y_bottom < y_top:
        return 0.0
    intersection = (x_right - x_left) * (y_bottom - y_top)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    return intersection / float(area1 + area2 - intersection)


# ── YOLO-based balloon detection ──────────────────────────────────────────────

def _process_with_yolo(images):
    results = []
    for page_idx, page in enumerate(images):
        img = np.array(page)
        # P13 fix: handle RGBA (4-channel) images from PyMuPDF
        if img.ndim == 3 and img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        elif img.ndim == 3 and img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        inference_results = yolo_model(img, verbose=False)
        detections = []
        for r in inference_results:
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = float(box.conf[0].cpu().numpy())
                if conf < 0.2:
                    continue
                w = x2 - x1
                h = y2 - y1
                aspect_ratio = w / h if h > 0 else 0
                if aspect_ratio < 0.7 or aspect_ratio > 1.4:
                    continue
                radius = min(w, h) / 2
                if radius < 10 or radius > 80:
                    continue

                ix1, iy1, ix2, iy2 = int(x1), int(y1), int(x2), int(y2)
                pad = 5
                crop = gray[
                    max(0, iy1 - pad): min(img.shape[0], iy2 + pad),
                    max(0, ix1 - pad): min(img.shape[1], ix2 + pad),
                ]
                if crop.size == 0:
                    continue

                _, thresh = cv2.threshold(
                    crop, 128, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
                cnts, _ = cv2.findContours(
                    thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                is_circular = any(
                    cv2.arcLength(c, True) > 0
                    and (4 * np.pi * cv2.contourArea(c) /
                         (cv2.arcLength(c, True) ** 2)) > 0.6
                    for c in cnts
                    if cv2.contourArea(c) >= 100
                )
                if not is_circular:
                    continue

                ocr_data = pytesseract.image_to_data(
                    crop, config="--psm 6",
                    output_type=pytesseract.Output.DICT,
                )
                best_text, best_conf = "", -1
                for k in range(len(ocr_data["text"])):
                    t = ocr_data["text"][k].strip()
                    c_ = float(ocr_data["conf"][k])
                    if t and c_ >= 20 and re.match(r"^[A-Za-z0-9]{1,4}$", t):
                        if c_ > best_conf:
                            best_conf, best_text = c_, t.upper()

                if best_text:
                    # P11 fix: use native image coords (was wrongly scaled to 1000px)
                    detections.append({
                        "box":            (ix1, iy1, ix2, iy2),
                        "x":              int(ix1 + w / 2),
                        "y":              int(iy1 + h / 2),
                        "text":           best_text,
                        "type":           "balloon",
                        "confidence":     round(conf * 100, 1),
                        "ocr_confidence": best_conf,
                        "page":           page_idx + 1,
                    })

        detections.sort(key=lambda d: d["confidence"], reverse=True)
        final = []
        for det in detections:
            if not any(
                compute_iou(det["box"], f["box"]) > 0.3 for f in final
            ):
                det.pop("box", None)
                final.append(det)
        results.extend(final)
    return results


# ── OpenCV-based balloon detection (fallback) ─────────────────────────────────

def _process_with_opencv(images):
    """
    Balloon detection using Contour Geometry Filtering.
    Filters for circularity, solidity, aspect ratio, and internal text.
    """
    results = []
    for page_idx, page in enumerate(images):
        img = np.array(page)

        # P13 fix: handle RGBA (4-channel) PDF renders
        if img.ndim == 3 and img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        elif img.ndim == 3 and img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        _, thresh = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # RETR_CCOMP gives hierarchy so we can check for child contours (text inside circle)
        cnts, hierarchy = cv2.findContours(
            thresh, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)

        page_balloons = []

        if hierarchy is not None:
            for i, cnt in enumerate(cnts):
                area = cv2.contourArea(cnt)
                perimeter = cv2.arcLength(cnt, True)
                if perimeter == 0:
                    continue

                # Circularity: 1.0 = perfect circle
                circularity = (4 * np.pi * area) / (perimeter ** 2)

                # Solidity: area vs convex hull area
                hull = cv2.convexHull(cnt)
                hull_area = cv2.contourArea(hull)
                solidity = float(area) / hull_area if hull_area > 0 else 0

                # Aspect ratio: should be ~1.0 for circles
                x, y, w, h = cv2.boundingRect(cnt)
                aspect_ratio = float(w) / h if h > 0 else 0

                # Apply geometry filters
                if not (
                    circularity > 0.70
                    and solidity > 0.85
                    and 0.8 <= aspect_ratio <= 1.2
                ):
                    continue

                # ✅ Fixed: correct hierarchy indexing
                # hierarchy shape: (1, N, 4) → [Next, Prev, First_Child, Parent]
                # First_Child == -1 means no child contours (no text inside)
                if hierarchy[0][i][2] == -1:
                    continue

                # Extract ROI with padding
                margin = 5
                # ✅ Fixed: correct shape indexing (shape[1]=width, shape[0]=height)
                x1 = max(0, x - margin)
                y1 = max(0, y - margin)
                x2 = min(gray.shape[1], x + w + margin)
                y2 = min(gray.shape[0], y + h + margin)
                roi = gray[y1:y2, x1:x2]

                if roi.size == 0:
                    continue

                # Run localised OCR on the balloon crop
                balloon_text = pytesseract.image_to_string(
                    roi, config="--psm 10"
                ).strip()

                # Only keep numeric text (balloon numbers)
                if balloon_text.isdigit():
                    page_balloons.append({
                        "text": balloon_text,
                        "x":    float(x + w / 2),
                        "y":    float(y + h / 2),
                        "w":    float(w),
                        "h":    float(h),
                        "page": page_idx + 1,
                    })

        results.append(page_balloons)

    return results


# ════════════════════════════════════════════════════════════════════════════
# ROUTES
# ════════════════════════════════════════════════════════════════════════════

# ── POST /upload ──────────────────────────────────────────────────────────────
@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400, detail="Only PDF files are accepted.")

    doc_id = str(uuid.uuid4())
    safe_name = f"{doc_id}_{file.filename}"
    pdf_path = UPLOAD_DIR / safe_name

    # Save PDF to disk
    content = await file.read()
    pdf_path.write_bytes(content)

    # Convert PDF → PIL images using PyMuPDF and keep fitz pages for native extraction
    try:
        fitz_doc = fitz.open(str(pdf_path))
        images = []
        fitz_pages = []          # P10 fix: keep pages for native text extraction
        zoom = 300 / 72          # 300 DPI
        matrix = fitz.Matrix(zoom, zoom)

        for page_idx in range(len(fitz_doc)):
            fitz_page = fitz_doc.load_page(page_idx)
            pix = fitz_page.get_pixmap(matrix=matrix)
            page_no = page_idx + 1
            img_path = UPLOAD_DIR / f"{doc_id}_page_{page_no}.png"
            pix.save(str(img_path))
            images.append(Image.open(str(img_path)))
            fitz_pages.append(fitz_page)  # store for native extraction

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"PDF conversion failed: {e}")

    page_count = len(images)
    page_width = images[0].width if images else 0
    page_height = images[0].height if images else 0

    all_balloons = []
    balloon_counter = 1

    for page_no, (pil_img, fitz_page) in enumerate(zip(images, fitz_pages), start=1):

        # P10 fix: try native vector text extraction first
        native_words = fitz_page.get_text('words')
        meaningful = [w for w in native_words if w[4].strip()]

        if len(meaningful) >= 5:
            logger.info("Page %d: native PDF extraction (%d words).", page_no, len(meaningful))
            detections = detect_from_pdf_page(fitz_page, dpi_scale=300.0 / 72.0)
        else:
            logger.info("Page %d: OCR fallback (%d native words found).", page_no, len(meaningful))
            # P13 fix: handle RGBA (4-channel) images
            img_np = np.array(pil_img)
            if img_np.ndim == 3 and img_np.shape[2] == 4:
                img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGBA2BGR)
            elif img_np.ndim == 3 and img_np.shape[2] == 3:
                img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            else:
                img_bgr = img_np
            detections = detect_annotations(img_bgr)

        logger.info("Page %d: %d annotation(s) detected.", page_no, len(detections))

        # Assign sequential balloon numbers and spread overlaps
        page_balloons = assign_balloon_numbers(
            detections, doc_id, page_no, start_no=balloon_counter)
        page_balloons = spread_overlapping_balloons(
            page_balloons, min_distance=40)

        balloon_counter += len(page_balloons)
        all_balloons.extend(page_balloons)

    # Persist document record
    doc_record = {
        "_id":         ObjectId(),
        "doc_id":      doc_id,
        "filename":    file.filename,
        "file_path":   str(pdf_path),
        "upload_time": datetime.utcnow(),
        "page_count":  page_count,
    }
    await documents_collection.insert_one(doc_record)

    # Persist balloons
    if all_balloons:
        for b in all_balloons:
            b["_id"] = ObjectId()
        await balloons_collection.insert_many(all_balloons)

    # Fetch persisted balloons for response
    saved_balloons = []
    async for b in balloons_collection.find({"document_id": doc_id}):
        saved_balloons.append(_serialize_balloon(b))

    return {
        "document_id": doc_id,
        "page_count":  page_count,
        "page_width":  page_width,
        "page_height": page_height,
        "balloons":    saved_balloons,
    }


# ── GET /document/{document_id} ───────────────────────────────────────────────
@app.get("/document/{document_id}")
async def get_document(document_id: str):
    doc = await documents_collection.find_one({"doc_id": document_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    doc = _serialize_doc(doc)

    balloons = []
    async for b in balloons_collection.find({"document_id": document_id}):
        balloons.append(_serialize_balloon(b))

    doc["balloons"] = balloons
    return doc


# ── GET /document/{document_id}/image/{page_no} ───────────────────────────────
@app.get("/document/{document_id}/image/{page_no}")
async def get_page_image(document_id: str, page_no: int):
    img_path = UPLOAD_DIR / f"{document_id}_page_{page_no}.png"
    if not img_path.exists():
        raise HTTPException(status_code=404, detail="Page image not found.")
    return FileResponse(str(img_path), media_type="image/png")


# ── POST /balloons ────────────────────────────────────────────────────────────
@app.post("/balloons")
async def create_balloon(payload: BalloonCreate):
    # P12 fix: use max(balloon_no)+1 instead of count+1 to avoid
    # duplicate numbers after a delete operation.
    pipeline = [
        {"$match":  {"document_id": payload.document_id}},
        {"$group":  {"_id": None, "max_no": {"$max": "$balloon_no"}}},
    ]
    cursor = balloons_collection.aggregate(pipeline)
    result = await cursor.to_list(length=1)
    new_no = (result[0]["max_no"] + 1) if result else 1

    balloon = {
        "_id":        ObjectId(),
        "document_id": payload.document_id,
        "balloon_no": new_no,
        "text":       payload.text,
        "type":       payload.type,
        "x":          payload.x,
        "y":          payload.y,
        "feature_x":  payload.feature_x,
        "feature_y":  payload.feature_y,
        "page":       payload.page,
        "units":      payload.units or ("mm" if payload.type == "Dimension" else ""),
        "description": "",
        "remarks":    "",
    }
    await balloons_collection.insert_one(balloon)
    balloon["id"] = str(balloon.pop("_id"))
    return balloon


# ── PUT /balloons/{balloon_id} ────────────────────────────────────────────────
@app.put("/balloons/{balloon_id}")
async def update_balloon(balloon_id: str, payload: BalloonUpdate):
    update_fields = {
        k: v for k, v in payload.model_dump().items() if v is not None
    }
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update.")

    result = await balloons_collection.update_one(
        {"_id": ObjectId(balloon_id)},
        {"$set": update_fields},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Balloon not found.")

    updated = await balloons_collection.find_one(
        {"_id": ObjectId(balloon_id)})
    return _serialize_balloon(updated)


# ── DELETE /balloons/{balloon_id} ─────────────────────────────────────────────
@app.delete("/balloons/{balloon_id}")
async def delete_balloon(balloon_id: str):
    result = await balloons_collection.delete_one(
        {"_id": ObjectId(balloon_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Balloon not found.")
    return {"deleted": balloon_id}


# ── GET /export/{document_id} ─────────────────────────────────────────────────
@app.get("/export/{document_id}")
async def export_document(document_id: str):
    balloons = []
    async for b in balloons_collection.find({"document_id": document_id}):
        b["id"] = str(b.pop("_id"))
        balloons.append(b)

    if not balloons:
        raise HTTPException(
            status_code=404,
            detail="No balloons found for this document.")

    out_path = str(EXPORT_DIR / f"{document_id}_balloons.xlsx")
    export_to_excel(balloons, out_path)

    return FileResponse(
        out_path,
        media_type=(
            "application/vnd.openxmlformats-officedocument"
            ".spreadsheetml.sheet"
        ),
        filename=f"balloons_{document_id}.xlsx",
    )


# ── POST /detect-existing-balloons ────────────────────────────────────────────
class DetectRequest(BaseModel):
    document_id: str


@app.post("/detect-existing-balloons")
async def detect_existing_balloons(req: DetectRequest):
    """
    Run the YOLO / OpenCV pipeline on stored page images to find
    pre-drawn balloons (circles with numbers) in the drawing.
    """
    page_no = 1
    pil_images = []

    while True:
        img_path = UPLOAD_DIR / f"{req.document_id}_page_{page_no}.png"
        if not img_path.exists():
            break
        pil_images.append(Image.open(str(img_path)))
        page_no += 1

    if not pil_images:
        raise HTTPException(
            status_code=404,
            detail="No stored images found for this document.")

    if USE_YOLO:
        results = _process_with_yolo(pil_images)
    else:
        results = _process_with_opencv(pil_images)

    return {
        "detected_balloons": results,
        "method": "yolo" if USE_YOLO else "opencv",
    }


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
