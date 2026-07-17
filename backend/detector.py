"""
detector.py — CAD annotation detector
"""

import re
import cv2
import numpy as np
import pytesseract
from typing import List, Dict, Any, Tuple, Optional


# ── Tunable constants ─────────────────────────────────────────────────────────
MIN_OCR_CONF = 45
MIN_NUMERIC_CONF = 15
MIN_MEANINGFUL_CHARS = 2
TITLE_BLOCK_FRAC = 0.85
BORDER_FRAC_X = 0.05
BORDER_FRAC_Y = 0.05
GROUP_X_GAP = 20
GROUP_Y_DELTA = 12
DEDUP_RADIUS = 25
NEAR_LINE_DIST = 80

_TITLE_BLOCK_REJECT = re.compile(
    r'ALL DIMENSIONS|IN\s+mm\b|DRAWN BY|CHECKED BY|APPROVED BY|CUSTOMER|MATERIAL|'
    r'HEAT TREATMENT|HARDNESS|DRAWING NO|SHEET|CUST FILE|REV\b|PVT\.?\s*LTD|'
    r'GEARS|LIBERTY|STEEL|TOTAL WT|NOTE:|NOTES:|TOLERANCE:\s|SCALE:|DRG\.|'
    r'^VIEW\s+[A-Z]|^SECTION\s|^SEC\.\s|\bQTY\b|\bNOS\.?\b(?!\s*\d)',
    re.IGNORECASE,
)

_ENGLISH_WORDS = re.compile(
    r'^(are|the|and|for|not|all|nos|with|this|that|from|into|each|item|date|rev)$',
    re.IGNORECASE,
)

_PUNCT_ARTIFACT = re.compile(r'^\d+[\)\.]$|^[\(\[\{]\d+$')
_CLEAN_PREFIX = re.compile(r'^[_\-\.\|\\\/ ]+')
_SLASH_JOINED = re.compile(r'^\d+\.?\d*\/\d+\.?\d*$')


def correct_ocr_text(text: str) -> str:
    t = text.strip()
    if not t:
        return t
    t = re.sub(r'^[oOQ0]\s*([1-7, 11, 12]\d*(?:\.\d+)?)$', r'Ø\1', t)
    t = re.sub(r'^[ø∅]\s*', 'Ø', t)
    t = re.sub(
        r'^(?:\+[-=]|\+\s*[-=]|\*[-=]|\*\s*[-=]|\+\/-\s*)\s*(\d)', r'±\1', t)
    t = re.sub(r'^\*\s*(\d+\.\d+)', r'±\1', t)
    t = re.sub(r'(\d+)\s*[o\*]$', r'\1°', t)
    return t


def _classify_text(text: str) -> Optional[str]:
    t = text.strip()
    if not t:
        return None

    clean = re.sub(r'[\s\W]', '', t)
    if not clean:
        return None

    if re.fullmatch(r'[A-Za-z]', clean):
        return None

    if _ENGLISH_WORDS.match(t):
        return None

    if _PUNCT_ARTIFACT.match(t):
        return None

    if _SLASH_JOINED.match(t):
        return None

    if re.search(r'^VIEW\s+[A-Z]|^SECTION\s|^SEC\.', t, re.IGNORECASE):
        return None

    if re.search(
        r'[±]'
        r'|\+\s*\d+[\.,]\d+'
        r'|[-\u2212]\s*\d+[\.,]\d+'
        r'|^\s*0\.\d+'
        r'|\(\s*[+\-]',
        t
    ):
        return "Tolerance"

    if re.search(r'\bRa\b|\bRz\b|\bRt\b|\bRq\b', t, re.IGNORECASE):
        return "Surface Finish"

    if re.search(r'^\s*0\.\d+\s+[A-Z]\s*$|[⊙⊖⊕⊗⌀○△□◇⊥∥∠]', t):
        return "GD&T"

    if re.search(
        r'[\d]'
        r'|[Øø∅]'
        r'|[Rr]\s*\d'
        r'|[Hh]\d'
        r'|\d+\s*[xX×]\s*\d'
        r'|\d+\s*°'
        r'|\d+\s*mm',
        t
    ):
        return "Dimension"

    if len(clean) >= 3:
        return "Note"

    return None


def _find_nearest_feature(
    tx: float, ty: float,
    lines: List[Tuple],
    contours: List,
) -> Tuple[float, float]:
    best_dist = float("inf")
    best_pt: Tuple[float, float] = (tx, ty)

    for x1, y1, x2, y2 in lines:
        for px, py in [(x1, y1), (x2, y2)]:
            d = (px - tx) ** 2 + (py - ty) ** 2
            if d < best_dist:
                best_dist = d
                best_pt = (float(px), float(py))

    for cnt in contours:
        M = cv2.moments(cnt)
        if M["m00"] != 0:
            cx = float(M["m10"] / M["m00"])
            cy = float(M["m01"] / M["m00"])
            d = (cx - tx) ** 2 + (cy - ty) ** 2
            if d < best_dist:
                best_dist = d
                best_pt = (cx, cy)

    return best_pt


def _group_tokens(
    raw_tokens: List[Dict],
    y_delta: int = GROUP_Y_DELTA,
    x_gap: int = GROUP_X_GAP,
) -> List[Dict]:
    if not raw_tokens:
        return []

    tokens = sorted(raw_tokens, key=lambda t: (t["cy"], t["x"]))
    groups: List[Dict] = []
    used = [False] * len(tokens)

    for i, tok in enumerate(tokens):
        if used[i]:
            continue
        group_text = tok["text"]
        gx1 = tok["x"]
        gy1 = tok["cy"]
        gx2 = tok["x"] + tok["w"]
        max_conf = tok["conf"]
        best_feat = (tok["feat_x"], tok["feat_y"])

        for j in range(i + 1, len(tokens)):
            if used[j]:
                continue
            other = tokens[j]
            dy = abs(other["cy"] - gy1)
            dx_gap = other["x"] - gx2
            if dy <= y_delta and 0 <= dx_gap <= x_gap:
                group_text += " " + other["text"]
                gx2 = other["x"] + other["w"]
                if other["conf"] > max_conf:
                    max_conf = other["conf"]
                    best_feat = (other["feat_x"], other["feat_y"])
                used[j] = True

        groups.append({
            "text": group_text.strip(),
            "x": float((gx1 + gx2) / 2.0),
            "y": float(gy1),
            "feat_x": float(best_feat[0]),
            "feat_y": float(best_feat[1]),
        })

    return groups


def _deduplicate(
    annotations: List[Dict],
    radius: float = DEDUP_RADIUS,
) -> List[Dict]:
    kept: List[Dict] = []
    for ann in annotations:
        duplicate = False
        for k in kept:
            if ((ann["x"] - k["x"]) ** 2 + (ann["y"] - k["y"]) ** 2) < radius ** 2:
                duplicate = True
                break
        if not duplicate:
            kept.append(ann)
    return kept


def _get_segmented_ocr_tokens(
    gray: np.ndarray,
    thresh: np.ndarray,
    scale_factor: float,
    x_min: int, x_max: int,
    y_min: int, y_max: int,
    lines: List[Tuple],
    contours: List,
    near_line_dist: int,
) -> List[Dict]:
    kernel_dilate = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 3))
    dilated = cv2.dilate(thresh, kernel_dilate, iterations=1)

    cnts, _ = cv2.findContours(
        dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    tokens = []
    img_h, img_w = gray.shape

    for cnt in cnts:
        x, y, w, h = cv2.boundingRect(cnt)

        if not (8 <= h <= 80 and 8 <= w <= 600):
            continue
        if y < y_min or (y + h) > y_max:
            continue
        if x < x_min or (x + w) > x_max:
            continue

        margin = 6
        x1 = max(0, x - margin)
        y1 = max(0, y - margin)
        x2 = min(img_w, x + w + margin)
        y2 = min(img_h, y + h + margin)

        crop = gray[y1:y2, x1:x2]
        if crop.size == 0:
            continue

        pad_val = 10
        crop_padded = cv2.copyMakeBorder(
            crop, pad_val, pad_val, pad_val, pad_val,
            cv2.BORDER_CONSTANT, value=255,
        )

        crop_resized = cv2.resize(
            crop_padded, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)

        crop_thresh = cv2.adaptiveThreshold(
            crop_resized, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            15, 5,
        )

        ocr_data = pytesseract.image_to_data(
            crop_thresh, config="--psm 7",
            output_type=pytesseract.Output.DICT,
        )

        for i in range(len(ocr_data["text"])):
            text = ocr_data["text"][i].strip()
            conf = float(ocr_data["conf"][i])

            if not text or conf < MIN_NUMERIC_CONF:
                continue

            c_left = ocr_data["left"][i]
            c_top = ocr_data["top"][i]
            c_width = ocr_data["width"][i]
            c_height = ocr_data["height"][i]

            g_left = int((c_left / 2.0) - pad_val + x1)
            g_top = int((c_top / 2.0) - pad_val + y1)
            g_width = int(c_width / 2.0)
            g_height = int(c_height / 2.0)
            g_cx = float(g_left + g_width / 2.0)
            g_cy = float(g_top + g_height / 2.0)

            is_dim_candidate = bool(re.search(r'[\dØø∅Rr]', text))

            if conf < MIN_OCR_CONF:
                if not is_dim_candidate:
                    continue
                near_line = False
                for lx1, ly1, lx2, ly2 in lines:
                    dx = lx2 - lx1
                    dy = ly2 - ly1
                    if dx == 0 and dy == 0:
                        d = ((g_cx - lx1) ** 2 + (g_cy - ly1) ** 2) ** 0.5
                    else:
                        t_val = max(
                            0.0,
                            min(1.0,
                                ((g_cx - lx1) * dx + (g_cy - ly1) * dy)
                                / (dx * dx + dy * dy)),
                        )
                        d = (
                            (g_cx - (lx1 + t_val * dx)) ** 2
                            + (g_cy - (ly1 + t_val * dy)) ** 2
                        ) ** 0.5
                    if d < near_line_dist:
                        near_line = True
                        break
                if not near_line:
                    continue

            if _TITLE_BLOCK_REJECT.search(text):
                continue

            feat_x, feat_y = _find_nearest_feature(
                g_cx, g_cy, lines, contours)

            tokens.append({
                "text":   text,
                "x":      g_left,
                "w":      g_width,
                "cy":     g_cy,
                "conf":   conf,
                "feat_x": float(feat_x),
                "feat_y": float(feat_y),
            })

    return tokens


# ── Public API ────────────────────────────────────────────────────────────────

def detect_annotations(image: np.ndarray) -> List[Dict[str, Any]]:
    """
    Detect CAD annotation text from a BGR page image.
    Always returns a list (empty if nothing found) — never None.
    """
    # ✅ Guard against bad input
    if image is None or image.size == 0:
        return []

    try:
        return _detect_annotations_impl(image)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(
            "detect_annotations failed: %s", e, exc_info=True)
        return []  # ✅ Never return None


def _detect_annotations_impl(image: np.ndarray) -> List[Dict[str, Any]]:
    """Core detection logic — separated so detect_annotations can catch all errors."""

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    img_h, img_w = gray.shape

    # Scale thresholds dynamically
    scale = img_h / 1200.0
    group_y_delta = int(max(6,  GROUP_Y_DELTA * scale))
    group_x_gap = int(max(15, GROUP_X_GAP * scale))
    dedup_radius = int(max(15, DEDUP_RADIUS * scale))
    near_line_dist = int(max(30, NEAR_LINE_DIST * scale))

    # ── Spatial exclusion zones ──────────────────────────────────────────────
    is_landscape = img_w > img_h
    current_title_block_frac = 0.97 if is_landscape else TITLE_BLOCK_FRAC

    y_min = int(img_h * BORDER_FRAC_Y)
    y_max = int(img_h * current_title_block_frac)
    x_min = int(img_w * BORDER_FRAC_X)
    x_max = int(img_w * (1.0 - BORDER_FRAC_X))

    # ── Structural features ──────────────────────────────────────────────────
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    raw_lines = cv2.HoughLinesP(
        edges, rho=1, theta=np.pi / 180,
        threshold=60, minLineLength=40, maxLineGap=10,
    )
    lines: List[Tuple] = []
    if raw_lines is not None:
        for ln in raw_lines:
            lines.append(tuple(int(v) for v in ln[0]))

    _, thresh = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    cnts, _ = cv2.findContours(
        thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = [
        c for c in cnts
        if 200 < cv2.contourArea(c) < img_w * img_h * 0.04
    ]

    # ── Segmented Crop-based OCR ─────────────────────────────────────────────
    raw_tokens = _get_segmented_ocr_tokens(
        gray=gray,
        thresh=thresh,
        scale_factor=1.5,
        x_min=x_min, x_max=x_max,
        y_min=y_min, y_max=y_max,
        lines=lines,
        contours=contours,
        near_line_dist=near_line_dist,
    )

    # ── Group adjacent tokens on the same line ───────────────────────────────
    grouped = _group_tokens(
        raw_tokens, y_delta=group_y_delta, x_gap=group_x_gap)

    # ── Classify and filter ──────────────────────────────────────────────────
    classified: List[Dict] = []
    for g in grouped:
        clean_text = _CLEAN_PREFIX.sub("", g["text"]).strip()
        clean_text = correct_ocr_text(clean_text)
        if not clean_text:
            continue
        if _TITLE_BLOCK_REJECT.search(clean_text):
            continue
        ann_type = _classify_text(clean_text)
        if ann_type is None:
            continue
        classified.append({
            "text":      clean_text,
            "type":      ann_type,
            "x":         float(round(g["x"],      1)),
            "y":         float(round(g["y"],      1)),
            "feature_x": float(round(g["feat_x"], 1)),
            "feature_y": float(round(g["feat_y"], 1)),
        })

    # ── Deduplicate ──────────────────────────────────────────────────────────
    results = _deduplicate(classified, radius=dedup_radius)

    return results  # ✅ Always a list
