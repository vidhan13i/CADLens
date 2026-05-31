from fastapi import FastAPI
from pydantic import BaseModel
import pytesseract
import cv2
import numpy as np
from pdf2image import convert_from_path
import re
import os

app = FastAPI()

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Try to load YOLO model, fallback to OpenCV if not found
try:
    from ultralytics import YOLO
    import logging
    # Suppress ultralytics logging
    logging.getLogger("ultralytics").setLevel(logging.WARNING)
    if os.path.exists("balloon_detector.pt"):
        model = YOLO("balloon_detector.pt")
        USE_YOLO = True
        print("Loaded YOLO balloon detector.")
    else:
        model = None
        USE_YOLO = False
        print("balloon_detector.pt not found. Falling back to OpenCV.")
except ImportError:
    model = None
    USE_YOLO = False
    print("ultralytics not installed. Falling back to OpenCV.")

class PDFRequest(BaseModel):
    file_path: str

def compute_iou(box1, box2):
    # box: (x1, y1, x2, y2)
    x_left = max(box1[0], box2[0])
    y_top = max(box1[1], box2[1])
    x_right = min(box1[2], box2[2])
    y_bottom = min(box1[3], box2[3])

    if x_right < x_left or y_bottom < y_top:
        return 0.0

    intersection_area = (x_right - x_left) * (y_bottom - y_top)
    box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
    box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])
    
    iou = intersection_area / float(box1_area + box2_area - intersection_area)
    return iou

def process_with_yolo(images):
    results = []
    
    for page_idx, page in enumerate(images):
        img = np.array(page)
        # Convert RGB to BGR for OpenCV
        if img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # YOLO Inference
        inference_results = model(img, verbose=False)
        
        detections = []
        for r in inference_results:
            boxes = r.boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = float(box.conf[0].cpu().numpy())
                
                # YOLO confidence threshold
                if conf < 0.2:
                    continue
                
                w = x2 - x1
                h = y2 - y1
                
                # 1. Aspect Ratio Validation
                aspect_ratio = w / h
                if aspect_ratio < 0.7 or aspect_ratio > 1.4:
                    continue
                
                # 2. Radius Validation (min 15, max 60 based on previous params)
                radius = min(w, h) / 2
                if radius < 10 or radius > 80:
                    continue
                
                # Crop and validate circularity
                ix1, iy1, ix2, iy2 = int(x1), int(y1), int(x2), int(y2)
                # Add a small padding
                pad = 5
                cx1 = max(0, ix1 - pad)
                cy1 = max(0, iy1 - pad)
                cx2 = min(img.shape[1], ix2 + pad)
                cy2 = min(img.shape[0], iy2 + pad)
                
                crop = gray[cy1:cy2, cx1:cx2]
                if crop.size == 0:
                    continue
                
                # Check circularity using simple thresholding and contours
                _, thresh = cv2.threshold(crop, 128, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
                contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                is_circular = False
                for cnt in contours:
                    area = cv2.contourArea(cnt)
                    if area < 100:
                        continue
                    perimeter = cv2.arcLength(cnt, True)
                    if perimeter == 0:
                        continue
                    circularity = 4 * np.pi * (area / (perimeter * perimeter))
                    if circularity > 0.6:  # Relaxed circularity for noisy scans
                        is_circular = True
                        break
                        
                if not is_circular:
                    continue
                
                # OCR ONLY inside the crop
                # Use psm 6 for single block of text or 10 for single char
                ocr_data = pytesseract.image_to_data(crop, config='--psm 6', output_type=pytesseract.Output.DICT)
                
                best_text = ""
                best_ocr_conf = -1
                
                for i in range(len(ocr_data['text'])):
                    text = ocr_data['text'][i].strip()
                    ocr_conf = float(ocr_data['conf'][i])
                    
                    if text and ocr_conf >= 20:
                        # Relaxed Regex Validation
                        if re.match(r"^[A-Za-z0-9]{1,4}$", text):
                            text = text.upper()
                            if ocr_conf > best_ocr_conf:
                                best_ocr_conf = ocr_conf
                                best_text = text
                
                if best_text:
                    x_center = ix1 + w / 2
                    y_center = iy1 + h / 2
                    
                    scale = 1000.0 / img.shape[1] # Map to frontend Page width={1000}
                    
                    detections.append({
                        "box": (ix1, iy1, ix2, iy2),
                        "x": int(x_center * scale),
                        "y": int(y_center * scale),
                        "text": best_text,
                        "type": "balloon",
                        "confidence": round(conf * 100, 1),
                        "ocr_confidence": best_ocr_conf
                    })
        
        # Deduplication using NMS / IoU
        detections.sort(key=lambda x: x['confidence'], reverse=True)
        final_detections = []
        
        for det in detections:
            overlap = False
            for f_det in final_detections:
                iou = compute_iou(det['box'], f_det['box'])
                if iou > 0.3: # If IoU > 0.3, they are likely the same balloon
                    overlap = True
                    break
            
            if not overlap:
                # Remove internal bounding box before returning
                det.pop('box', None)
                final_detections.append(det)
                
        results.extend(final_detections)
        
    return results

def process_with_opencv(images):
    results = []
    
    for page in images:
        img = np.array(page)
        # Convert RGB to BGR for OpenCV
        if img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        blurred = cv2.medianBlur(gray, 5)
        circles = cv2.HoughCircles(
            blurred, 
            cv2.HOUGH_GRADIENT, 
            dp=1.2, 
            minDist=30, 
            param1=50, 
            param2=45, # Relaxed param2 to catch more circles
            minRadius=15, 
            maxRadius=60
        )

        detected_balloons = []
        if circles is not None:
            circles = np.uint16(np.around(circles))
            for i in circles[0, :]:
                x_center, y_center, r = i[0], i[1], i[2]
                
                x1 = int(max(0, x_center - r))
                y1 = int(max(0, y_center - r))
                x2 = int(min(img.shape[1], x_center + r))
                y2 = int(min(img.shape[0], y_center + r))
                
                roi = gray[y1:y2, x1:x2]
                if roi.size == 0:
                    continue
                
                ocr_data = pytesseract.image_to_data(roi, config='--psm 6', output_type=pytesseract.Output.DICT)
                
                best_text = ""
                best_ocr_conf = -1
                
                for idx in range(len(ocr_data['text'])):
                    text = ocr_data['text'][idx].strip()
                    ocr_conf = float(ocr_data['conf'][idx])
                    
                    if text and ocr_conf >= 20:
                        # Relaxed Regex Validation
                        if re.match(r"^[A-Za-z0-9]{1,4}$", text):
                            text = text.upper()
                            if ocr_conf > best_ocr_conf:
                                best_ocr_conf = ocr_conf
                                best_text = text
                
                if best_text:
                    scale = 1000.0 / img.shape[1] # Map to frontend Page width={1000}
                    results.append({
                        "x": int(x_center * scale),
                        "y": int(y_center * scale),
                        "text": best_text,
                        "type": "balloon",
                        "confidence": 50.0, # Placeholder for fallback YOLO conf
                        "ocr_confidence": best_ocr_conf
                    })
                    detected_balloons.append((x_center, y_center, r))

        # We keep the old dimension logic for OpenCV fallback if desired, 
        # but the prompt specifically wants to ONLY detect balloons.
        # We will omit the full-page OCR dimension detection to match the new scope.

    return results

@app.post("/process")
def process_pdf(req: PDFRequest):
    images = convert_from_path(req.file_path)
    
    if USE_YOLO:
        return process_with_yolo(images)
    else:
        return process_with_opencv(images)