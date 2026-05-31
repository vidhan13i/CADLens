"""
detector.py — CAD annotation detector
Improvements over v1:
  • Spatial exclusion of title-block (bottom 18%) and border gutters
  • Token grouping: adjacent OCR tokens on the same line are merged
  • Stricter quality filters (min 2 meaningful chars, conf >= 45)
  • Richer classification regexes: R\d, Ø\d, H/h fit codes, section labels
  • Nearby-detection deduplication (50 px radius)
  • All coords guaranteed plain Python float for pymongo
"""

import re
import cv2
import numpy as np
import pytesseract
from typing import List, Dict, Any, Tuple, Optional


# ── Tunable constants ─────────────────────────────────────────────────────────
MIN_OCR_CONF = 20           # confidence for text tokens (words, R-nums, etc.)
MIN_NUMERIC_CONF = 15       # lower confidence allowed ONLY for pure-numeric tokens near dim lines
MIN_MEANINGFUL_CHARS = 1    # allow single-digit dims like '1', '2', '4'
TITLE_BLOCK_FRAC = 0.85
BORDER_FRAC_X = 0.03
BORDER_FRAC_Y = 0.03
GROUP_X_GAP = 20
GROUP_Y_DELTA = 12
DEDUP_RADIUS = 25
NEAR_LINE_DIST = 80         # px — numeric token within this dist of a dim line = valid

# Phrases / patterns that belong to the title block or frame — reject everywhere
_TITLE_BLOCK_REJECT = re.compile(
    r'ALL DIMENSIONS|IN\s+mm\b|DRAWN BY|CHECKED BY|APPROVED BY|CUSTOMER|MATERIAL|'
    r'HEAT TREATMENT|HARDNESS|DRAWING NO|SHEET|CUST FILE|REV\b|PVT\.?\s*LTD|'
    r'GEARS|LIBERTY|STEEL|TOTAL WT|NOTE:|NOTES:|TOLERANCE:\s|SCALE:|DRG\.|'
    r'^VIEW\s+[A-Z]|^SECTION\s|^SEC\.\s|\bQTY\b|\bNOS\.?\b(?!\s*\d)',
    re.IGNORECASE,
)

# Common English words that OCR picks up from notes/labels — never a CAD annotation
_ENGLISH_WORDS = re.compile(
    r'^(are|the|and|for|not|all|nos|with|this|that|from|into|each|item|date|rev)$',
    re.IGNORECASE,
)

# Trailing punctuation artifacts: '1)', '2.', '(3' etc.
_PUNCT_ARTIFACT = re.compile(r'^\d+[\)\.]$|^[\(\[\{]\d+$')

# Strip common OCR artefact chars from the start of a token
_CLEAN_PREFIX = re.compile(r'^[_\-\.\|\\\/ ]+')

# Slash-joined tokens like '30/10' are OCR merges of two separate dims — reject
_SLASH_JOINED = re.compile(r'^\d+\.?\d*\/\d+\.?\d*$')



# ── Text classification ───────────────────────────────────────────────────────

def _classify_text(text: str) -> Optional[str]:
    """
    Classify a CAD annotation string.
    Returns None only for clearly non-annotation content (pure letters like 'C', 'V').
    In CAD drawings, single digits like '1', '2', '4' ARE valid dimension values.
    """
    t = text.strip()
    if not t:
        return None

    clean = re.sub(r'[\s\W]', '', t)   # alphanumeric only for length check
    if not clean:
        return None

    # Skip pure single letters (section/view markers: 'A', 'B', 'C', 'D')
    # But allow single digits — '1', '2' etc. are valid CAD dimensions
    if re.fullmatch(r'[A-Za-z]', clean):
        return None

    # Skip common English words OCR reads from notes/labels
    if _ENGLISH_WORDS.match(t):
        return None

    # Skip punctuation artifacts like '1)', '2.', '(3'
    if _PUNCT_ARTIFACT.match(t):
        return None

    # Slash-joined OCR artifact  (30/10, 15/5 …)
    if _SLASH_JOINED.match(t):
        return None

    # VIEW / SECTION labels
    if re.search(r'^VIEW\s+[A-Z]|^SECTION\s|^SEC\.', t, re.IGNORECASE):
        return None

    # ── Tolerance FIRST — '0.150' → Tolerance not Dimension
    if re.search(
        r'[±]'
        r'|\+\s*\d+[\.,]\d+'
        r'|[-\u2212]\s*\d+[\.,]\d+'
        r'|^\s*0\.\d+'           # bare decimal  0.150, 0.05 …
        r'|\(\s*[+\-]',
        t
    ):
        return "Tolerance"

    # ── Surface Finish
    if re.search(r'\bRa\b|\bRz\b|\bRt\b|\bRq\b', t, re.IGNORECASE):
        return "Surface Finish"

    # ── GD&T
    if re.search(r'^\s*0\.\d+\s+[A-Z]\s*$|[⊙⊖⊕⊗⌀○△□◇⊥∥∠]', t):
        return "GD&T"

    # ── Dimension — broad match covers all numeric CAD annotations
    if re.search(
        r'[\d]'                    # any digit — covers '20', '1', 'R3', 'Ø39'
        r'|[Øø∅]'
        r'|[Rr]\s*\d'
        r'|[Hh]\d'
        r'|\d+\s*[xX×]\s*\d'
        r'|\d+\s*°'
        r'|\d+\s*mm',
        t
    ):
        return "Dimension"

    # ── General note: 3+ meaningful chars
    if len(clean) >= 3:
        return "Note"

    return None


# ── Nearest structural feature ────────────────────────────────────────────────

def _find_nearest_feature(
    tx: float, ty: float,
    lines: List[Tuple],
    contours: List,
) -> Tuple[float, float]:
    """Return (feature_x, feature_y) — closest line endpoint or contour centroid."""
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


# ── Token grouping ────────────────────────────────────────────────────────────

def _group_tokens(raw_tokens: List[Dict], y_delta: int = GROUP_Y_DELTA, x_gap: int = GROUP_X_GAP) -> List[Dict]:
    """
    Merge adjacent OCR tokens that are on the same line and close horizontally.
    This rebuilds 'Ø39 H8 (+0.039' into a single annotation string.
    """
    if not raw_tokens:
        return []

    # sort by top-y, then left-x
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


# ── Deduplication ─────────────────────────────────────────────────────────────

def _deduplicate(annotations: List[Dict], radius: float = DEDUP_RADIUS) -> List[Dict]:
    """Remove annotations whose centres are within `radius` px of a kept one."""
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


# ── Public API ────────────────────────────────────────────────────────────────

def detect_annotations(image: np.ndarray) -> List[Dict[str, Any]]:
    """
    Detect CAD annotation text from a BGR page image.

    Returns list of dicts:
        {text, type, x, y, feature_x, feature_y}
    All numeric fields are plain Python float — safe for MongoDB.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    img_h, img_w = gray.shape

    # Scale thresholds dynamically based on image height (normalized to 1200px baseline)
    scale = img_h / 1200.0
    group_y_delta = int(max(6, GROUP_Y_DELTA * scale))
    group_x_gap = int(max(15, GROUP_X_GAP * scale))
    dedup_radius = int(max(15, DEDUP_RADIUS * scale))
    near_line_dist = int(max(30, NEAR_LINE_DIST * scale))

    # ── Spatial exclusion zones ──────────────────────────────────────────────
    # Landscape drawings use the full vertical area; portrait drawings standardly have title blocks at bottom
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

    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    cnts, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = [c for c in cnts if 200 < cv2.contourArea(c) < img_w * img_h * 0.04]

    # ── OCR preprocessing ────────────────────────────────────────────────────
    # Upscale for better OCR on small text
    scale_factor = 1.5
    enlarged = cv2.resize(gray, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)

    # Sharpen
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    sharpened = cv2.filter2D(enlarged, -1, kernel)

    # Adaptive threshold — clean black/white for Tesseract
    processed = cv2.adaptiveThreshold(
        sharpened, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31, 10
    )

    # ── Full-page OCR ────────────────────────────────────────────────────────
    # Use PSM 11 (Sparse text) which is far superior for scattered CAD blueprint labels than PSM 6 (Block)
    ocr = pytesseract.image_to_data(
        processed, config="--psm 11", output_type=pytesseract.Output.DICT
    )
    n = len(ocr["text"])

    raw_tokens: List[Dict] = []

    def _near_any_line(cx: float, cy: float) -> bool:
        """True if (cx,cy) is within near_line_dist of any detected dimension line."""
        for x1, y1, x2, y2 in lines:
            dx, dy = x2 - x1, y2 - y1
            if dx == dy == 0:
                d = ((cx - x1) ** 2 + (cy - y1) ** 2) ** 0.5
            else:
                t = max(0.0, min(1.0, ((cx - x1) * dx + (cy - y1) * dy) / (dx * dx + dy * dy)))
                d = ((cx - (x1 + t * dx)) ** 2 + (cy - (y1 + t * dy)) ** 2) ** 0.5
            if d < near_line_dist:
                return True
        return False

    _IS_PURE_NUMERIC = re.compile(r'^\d+(\.\d+)?$')

    for i in range(n):
        text = ocr["text"][i].strip()
        conf = float(ocr["conf"][i])

        if not text:
            continue

        is_pure_num = bool(_IS_PURE_NUMERIC.match(text))
        is_dim_candidate = bool(re.search(r'[\dØø∅Rr]', text))

        # Filter out extremely low-confidence tokens (background noise)
        if conf < MIN_NUMERIC_CONF:
            continue

        # If it has moderate confidence but is less than MIN_OCR_CONF, allow it if it looks like a dimension near a line
        if conf < MIN_OCR_CONF:
            if not is_dim_candidate:
                continue
            # Must be near a structural line to prevent random character noise
            # (Note: we bypass this for high-confidence tokens so text notes aren't discarded)
            left   = int(ocr["left"][i]   / scale_factor)
            top    = int(ocr["top"][i]    / scale_factor)
            width  = int(ocr["width"][i]  / scale_factor)
            height = int(ocr["height"][i] / scale_factor)
            cx_tok = float(left + width  / 2.0)
            cy_tok = float(top  + height / 2.0)
            if not _near_any_line(cx_tok, cy_tok):
                continue

        left   = int(ocr["left"][i]   / scale_factor)
        top    = int(ocr["top"][i]    / scale_factor)
        width  = int(ocr["width"][i]  / scale_factor)
        height = int(ocr["height"][i] / scale_factor)
        cx_tok = float(left + width  / 2.0)
        cy_tok = float(top  + height / 2.0)

        # ── Spatial filter ───────────────────────────────────────────────────
        if top < y_min or top > y_max:
            continue
        if left < x_min or left > x_max:
            continue

        # ── Title-block boilerplate reject ───────────────────────────────────
        if _TITLE_BLOCK_REJECT.search(text):
            continue

        feat_x, feat_y = _find_nearest_feature(cx_tok, cy_tok, lines, contours)

        raw_tokens.append({
            "text":   text,
            "x":      left,
            "w":      width,
            "cy":     cy_tok,
            "conf":   conf,
            "feat_x": float(feat_x),
            "feat_y": float(feat_y),
        })

    # ── Group adjacent tokens on the same line ───────────────────────────────
    grouped = _group_tokens(raw_tokens, y_delta=group_y_delta, x_gap=group_x_gap)

    # ── Classify and filter ──────────────────────────────────────────────────
    classified: List[Dict] = []
    for g in grouped:
        # Clean OCR artefact prefix chars (_-R30 → R30)
        clean_text = _CLEAN_PREFIX.sub("", g["text"]).strip()
        if not clean_text:
            continue
        # Reject title-block boilerplate that slipped through grouping
        if _TITLE_BLOCK_REJECT.search(clean_text):
            continue
        ann_type = _classify_text(clean_text)
        if ann_type is None:
            continue   # skip unclassifiable / too-short tokens
        classified.append({
            "text":      clean_text,
            "type":      ann_type,
            "x":         float(round(g["x"],      1)),
            "y":         float(round(g["y"],      1)),
            "feature_x": float(round(g["feat_x"], 1)),
            "feature_y": float(round(g["feat_y"], 1)),
        })

    # ── Deduplicate overlapping annotations ──────────────────────────────────
    results = _deduplicate(classified, radius=dedup_radius)

    return results
