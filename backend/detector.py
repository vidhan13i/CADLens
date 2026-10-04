"""
detector.py v2 — Hybrid CAD Annotation Detector
================================================
PRIMARY  : detect_from_pdf_page(fitz_page, dpi_scale)
           Native vector text from PyMuPDF — instant, 100% accurate for digital PDFs.
FALLBACK : detect_annotations(image_bgr)
           Full-page OCR pipeline for scanned / raster-embedded drawings.

Fixes vs v1:
  P1  — cv2.RETR_EXTERNAL dropped all inside-border contours → replaced with full-page OCR
  P4  — loose [\\d] classifier produced false Dimension labels → strict engineering patterns
  P5  — title block exclusion was disabled for landscape → now 0.78 for all orientations
  P6  — broken regex [1-7, 11, 12] in correct_ocr_text → proper alternation
  P7  — MIN_NEAR_LINE_CONF was 15, letting hallucinations through → raised to 40
  P8  — no structured field parsing → _parse_annotation_fields() added
  P9  — per-contour pytesseract loop (500+ OS processes) → single full-page OCR call
  P10 — ignored native PDF text → detect_from_pdf_page() added as primary path
"""

import re
import math
from typing import List, Dict, Any, Tuple, Optional

import cv2
import numpy as np
import pytesseract


# ─── Tunable constants ────────────────────────────────────────────────────────
MIN_OCR_CONF       = 50    # v1: 45 — higher = fewer line/arrow hallucinations
MIN_NEAR_LINE_CONF = 40    # v1: 15 — was letting through OCR noise on CAD lines
DEDUP_RADIUS       = 30    # pixels in image space
BORDER_FRAC_X      = 0.04  # 4% left + right border exclusion (grid zone)
BORDER_FRAC_Y      = 0.04  # 4% top + bottom border exclusion
TITLE_BLOCK_FRAC   = 0.78  # v1: 0.97 for landscape — now 0.78 for all orientations
GROUP_Y_DELTA      = 10    # px: same-line vertical tolerance for OCR grouping
GROUP_X_GAP        = 25    # px: horizontal gap allowed within a token group
NEAR_LINE_DIST     = 60    # px: distance from HoughLine to count token as near-line
MIN_NATIVE_WORDS   = 5     # if PDF has fewer meaningful words, use OCR fallback


# ─── Regex helpers ────────────────────────────────────────────────────────────
_TITLE_BLOCK_REJECT = re.compile(
    r'ALL DIMENSIONS|IN\s+mm\b|DRAWN\s*BY|CHECKED\s*BY|APPROVED\s*BY|CUSTOMER|'
    r'MATERIAL|HEAT\s*TREATMENT|HARDNESS|DRAWING\s*NO|SHEET|CUST\s*FILE|'
    r'\bREV\b|PVT\.?\s*LTD|GEARS|LIBERTY|STEEL|TOTAL\s*WT|'
    r'^NOTE\s*:|^NOTES\s*:|TOLERANCE\s*:|SCALE\s*:|DRG\.|'
    r'^VIEW\s+[A-Z]|^SECTION\s|^SEC\.\s|\bQTY\b|\bNOS\.?\b(?!\s*\d)',
    re.IGNORECASE | re.MULTILINE,
)

_SECTION_VIEW = re.compile(
    r'^(?:VIEW|SECTION|SEC\.)\s+[A-Z]|^[A-Z]-[A-Z]$',
    re.IGNORECASE,
)

_ENGLISH_WORDS = re.compile(
    r'^(?:are|the|and|for|not|all|nos|with|this|that|from|into|each|item|'
    r'date|rev|total|details|bracket|ratna|liberty|steel|sheet)$',
    re.IGNORECASE,
)

_PUNCT_ONLY  = re.compile(r'^[\W_]+$')
_CLEAN_PREFIX = re.compile(r'^[_\-\.\|\\\/\s]+')

# Strict engineering dimension patterns (P4 fix — replaces loose [\d])
_DIM_PATTERNS = re.compile(
    r'[Øøø∅]\s*\d'           # Diameter:  Ø50, ø12
    r'|[Rr]\s*\d'             # Radius:    R6, r3
    r'|[Mm]\d+\s*[xX×]'      # Thread:    M10x1.5, M6x1
    r'|[Hh]\d'                # Fit:       H8, h7
    r'|\d+\.\d+'              # Decimal:   39.5, 0.150  (clearly dimensional)
    r'|\d+\s*°'               # Angle:     45°, 30°
    r'|\d+\s*mm'              # With unit: 50mm, 100mm
    r'|\d+\s*[Ii][Nn][Cc][Hh]' # With unit: 2inch
    r'|±\s*\d'                # Symmetric tolerance: ±0.05
    r'|\+\s*\d[\d\.]*\s*[/\\]\s*-\s*\d'  # Bilateral: +0.039/-0.000
    r'|[Dd][Ii][Aa]\.?\s*\d'  # Dia prefix: Dia 50, DIA50
)

_SURFACE_FINISH = re.compile(r'\b(?:Ra|Rz|Rt|Rq)\b', re.IGNORECASE)
_GDNT_SYMBOLS   = re.compile(r'[⊙⊖⊕⊗⌀○△□◇⊥∥∠⌖]')
_GDNT_PATTERN   = re.compile(r'^\s*0\.\d+\s+[A-Z]\s*$')


# ═════════════════════════════════════════════════════════════════════════════
#  STRUCTURED FIELD PARSER  (P8 fix)
# ═════════════════════════════════════════════════════════════════════════════

def _parse_annotation_fields(text: str, ann_type: str) -> Dict[str, str]:
    """
    Extract nominal_value, tolerances, surface_finish, etc. from annotation text.
    Returns a dict whose keys match the Balloon model's optional fields.
    """
    fields: Dict[str, str] = {
        'nominal_value':   '',
        'tolerance_upper': '',
        'tolerance_lower': '',
        'surface_finish':  '',
        'process':         '',
        'datum_ref':       '',
        'tolerance_zone':  '',
        'quantity':        '',
        'material':        '',
        'description':     '',
        'remarks':         '',
    }
    t = text.strip()

    if ann_type == 'Surface Finish':
        m = re.search(r'(Ra|Rz|Rt|Rq)\s*(\d+\.?\d*)', t, re.IGNORECASE)
        if m:
            fields['surface_finish'] = f'{m.group(1).upper()} {m.group(2)}'
            fields['nominal_value']  = m.group(2)
        return fields

    if ann_type == 'GD&T':
        # e.g. "⊥ 0.05 A-B" or "0.05 A"
        m = re.search(r'(\d+\.?\d+)\s+([A-Z](?:-[A-Z])*)', t)
        if m:
            fields['tolerance_zone'] = m.group(1)
            fields['datum_ref']      = m.group(2)
        return fields

    if ann_type == 'Tolerance':
        # Bilateral: +0.039 / -0.000
        m_bi = re.search(r'\+\s*(\d+\.?\d*)\s*[/\\]\s*-?\s*(\d+\.?\d*)', t)
        if m_bi:
            fields['tolerance_upper'] = f'+{m_bi.group(1)}'
            fields['tolerance_lower'] = f'-{m_bi.group(2)}'
            fields['tolerance_zone']  = m_bi.group(1)
        # Symmetric ±
        m_sym = re.search(r'[±]\s*(\d+\.?\d*)', t)
        if m_sym:
            fields['tolerance_zone']  = m_sym.group(1)
            fields['tolerance_upper'] = f'+{m_sym.group(1)}'
            fields['tolerance_lower'] = f'-{m_sym.group(1)}'
        # Leading decimal (0.150)
        if not m_bi and not m_sym:
            m_dec = re.search(r'^0\.(\d+)', t)
            if m_dec:
                fields['tolerance_zone'] = t
        return fields

    if ann_type == 'Dimension':
        # Diameter: Ø50, ø50, Dia 50, DIA50mm
        m_dia = re.search(r'(?:[Øøø∅]|[Dd][Ii][Aa]\.?)\s*(\d+\.?\d*)', t)
        if m_dia:
            fields['nominal_value'] = m_dia.group(1)
            return fields
        # Radius: R6, r3.5
        m_rad = re.search(r'[Rr]\s*(\d+\.?\d*)', t)
        if m_rad:
            fields['nominal_value'] = m_rad.group(1)
            return fields
        # Thread: M10x1.5
        m_thr = re.search(r'[Mm](\d+)\s*[xX×]\s*(\d+\.?\d*)', t)
        if m_thr:
            fields['nominal_value'] = f'M{m_thr.group(1)}x{m_thr.group(2)}'
            return fields
        # Fit code: 50H8
        m_fit = re.search(r'(\d+\.?\d*)\s*([HhKkNnPpFfEeGg]\d+)', t)
        if m_fit:
            fields['nominal_value'] = m_fit.group(1)
            return fields
        # Decimal or plain number + optional unit
        m_num = re.search(r'(\d+\.?\d*)\s*(?:mm|°)?', t)
        if m_num:
            fields['nominal_value'] = m_num.group(1)
        return fields

    if ann_type == 'Note':
        m_qty = re.search(r'(\d+)\s*[Nn]os?\.?', t)
        if m_qty:
            fields['quantity'] = m_qty.group(1)
        fields['description'] = t
        return fields

    return fields


# ═════════════════════════════════════════════════════════════════════════════
#  TEXT CLASSIFIER  (strict — P4 fix)
# ═════════════════════════════════════════════════════════════════════════════

def _classify_text_strict(
    text: str,
    require_engineering: bool = True,
) -> Optional[str]:
    """
    Classify text as an engineering annotation type.

    Args:
        text: raw annotation text string
        require_engineering: True for OCR fallback path (standalone integers
            too ambiguous without engineering prefix). False for native PDF
            path (numbers in the drawing zone are real dimensions).

    Returns:
        Annotation type string, or None if not an annotation.
    """
    t = text.strip()
    if not t:
        return None

    clean = re.sub(r'[\s\W]', '', t)
    if not clean:
        return None

    # Single letter → section/datum marker, not an annotation
    if re.fullmatch(r'[A-Za-z]', clean):
        return None

    # Single digit → border grid reference, not a dimension
    if re.fullmatch(r'\d', clean):
        return None

    # Section/view labels: "VIEW C", "SECTION A-A", "A-A"
    if _SECTION_VIEW.search(t):
        return None

    if _ENGLISH_WORDS.match(t):
        return None

    if _PUNCT_ONLY.match(t):
        return None

    if _TITLE_BLOCK_REJECT.search(t):
        return None

    # Surface finish
    if _SURFACE_FINISH.search(t):
        return 'Surface Finish'

    # GD&T
    if _GDNT_SYMBOLS.search(t) or _GDNT_PATTERN.match(t):
        return 'GD&T'

    # Tolerance patterns
    if re.search(
        r'[±]'
        r'|\+\s*\d+[\.,]\d+.*[/\\]'
        r'|^\s*0\.\d{2,}',
        t,
    ):
        return 'Tolerance'

    # Engineering dimension patterns (P4 fix — NOT just any digit)
    if _DIM_PATTERNS.search(t):
        return 'Dimension'

    # Standalone integers: allowed in native PDF path (they're in drawing zone)
    # Rejected in OCR path (too ambiguous without engineering prefix)
    if re.fullmatch(r'\d+', clean):
        return None if require_engineering else 'Dimension'

    # Multi-char text → Note
    if len(clean) >= 3:
        return 'Note'

    return None


def _correct_ocr_text(text: str) -> str:
    """Fix common OCR misreads on CAD drawings."""
    t = text.strip()
    if not t:
        return t
    # "O50" or "Q50" → "Ø50"  (P6 fix: was [1-7, 11, 12] — wrong char-class)
    t = re.sub(r'^[oOQ]\s*(\d+\.?\d*)$', r'Ø\1', t)
    # Lowercase ø/∅ → Ø
    t = re.sub(r'^[ø∅]\s*', 'Ø', t)
    # "+/-" variants → "±"
    t = re.sub(r'^(?:\+[-=]|\+/-|\+-)\s*(\d)', r'±\1', t)
    # Trailing letter "o" → degree symbol
    t = re.sub(r'(\d+)\s*o$', r'\1°', t)
    return t


# ═════════════════════════════════════════════════════════════════════════════
#  DEDUPLICATION
# ═════════════════════════════════════════════════════════════════════════════

def _deduplicate(
    annotations: List[Dict],
    radius: float = DEDUP_RADIUS,
) -> List[Dict]:
    kept: List[Dict] = []
    for ann in annotations:
        if not any(
            math.hypot(ann['x'] - k['x'], ann['y'] - k['y']) < radius
            for k in kept
        ):
            kept.append(ann)
    return kept


# ═════════════════════════════════════════════════════════════════════════════
#  PATH 1 — NATIVE PDF TEXT EXTRACTION  (P10 fix — PRIMARY PATH)
# ═════════════════════════════════════════════════════════════════════════════

def detect_from_pdf_page(
    page: Any,
    dpi_scale: float = 300.0 / 72.0,
) -> List[Dict[str, Any]]:
    """
    Extract CAD annotations directly from a PyMuPDF page's embedded vector text.

    Instant and 100% accurate for digital CAD PDFs (AutoCAD, SolidWorks, CATIA).
    Falls through gracefully for scanned drawings (returns empty list → caller
    should use OCR fallback).

    Args:
        page:      pymupdf.Page object
        dpi_scale: multiply PDF points (at 72 dpi) to get image pixel coords
                   at the render DPI. Default 300/72 ≈ 4.167 for 300 dpi.

    Returns:
        List of annotation dicts (text, type, x, y, feature_x, feature_y,
        + structured fields).
    """
    page_w: float = page.rect.width
    page_h: float = page.rect.height

    # Exclusion zones in PDF points
    x_min = page_w * BORDER_FRAC_X
    x_max = page_w * (1.0 - BORDER_FRAC_X)
    y_min = page_h * BORDER_FRAC_Y
    y_max = page_h * TITLE_BLOCK_FRAC  # P5 fix: was 0.97 for landscape

    # words → (x0, y0, x1, y1, text, block_no, line_no, word_no)
    raw_words = page.get_text('words')

    # Group words into lines using (block_no, line_no)
    line_map: Dict[Tuple, List] = {}
    for w in raw_words:
        key = (int(w[5]), int(w[6]))
        line_map.setdefault(key, []).append(w)

    annotations: List[Dict] = []

    for _key, words in line_map.items():
        words_s = sorted(words, key=lambda w: w[0])  # sort by x0

        lx0 = min(w[0] for w in words_s)
        ly0 = min(w[1] for w in words_s)
        lx1 = max(w[2] for w in words_s)
        ly1 = max(w[3] for w in words_s)

        cx_pt = (lx0 + lx1) / 2.0
        cy_pt = (ly0 + ly1) / 2.0

        # Spatial exclusion (in PDF points)
        if cx_pt < x_min or cx_pt > x_max:
            continue
        if cy_pt < y_min or cy_pt > y_max:
            continue

        line_text = ' '.join(w[4] for w in words_s).strip()
        if not line_text:
            continue

        line_text = _CLEAN_PREFIX.sub('', line_text).strip()
        if not line_text:
            continue

        # Native PDF path: allow standalone integers (they're in drawing zone)
        ann_type = _classify_text_strict(line_text, require_engineering=False)
        if ann_type is None:
            continue

        cx_img = round(cx_pt * dpi_scale, 1)
        cy_img = round(cy_pt * dpi_scale, 1)

        fields = _parse_annotation_fields(line_text, ann_type)

        annotations.append({
            'text':      line_text,
            'type':      ann_type,
            'x':         cx_img,
            'y':         cy_img,
            'feature_x': cx_img,
            'feature_y': cy_img,
            **fields,
        })

    return _deduplicate(annotations, radius=DEDUP_RADIUS * dpi_scale)


# ═════════════════════════════════════════════════════════════════════════════
#  PATH 2 — FULL-PAGE OCR  (P1 + P9 fix — FALLBACK for scanned drawings)
# ═════════════════════════════════════════════════════════════════════════════

def _find_nearest_feature(
    tx: float, ty: float,
    lines: List[Tuple],
    contours: List,
) -> Tuple[float, float]:
    """Find nearest geometry point (line endpoint or contour centroid) to tx, ty."""
    best_dist = float('inf')
    best_pt: Tuple[float, float] = (tx, ty)

    for x1, y1, x2, y2 in lines:
        for px, py in [(x1, y1), (x2, y2)]:
            d = (px - tx) ** 2 + (py - ty) ** 2
            if d < best_dist:
                best_dist = d
                best_pt = (float(px), float(py))

    for cnt in contours:
        M = cv2.moments(cnt)
        if M['m00'] != 0:
            cx = float(M['m10'] / M['m00'])
            cy = float(M['m01'] / M['m00'])
            d = (cx - tx) ** 2 + (cy - ty) ** 2
            if d < best_dist:
                best_dist = d
                best_pt = (cx, cy)

    return best_pt


def _group_tokens(
    raw_tokens: List[Dict],
    y_delta: int = GROUP_Y_DELTA,
    x_gap:   int = GROUP_X_GAP,
) -> List[Dict]:
    """Group adjacent OCR tokens on the same line into single annotation tokens."""
    if not raw_tokens:
        return []

    tokens = sorted(raw_tokens, key=lambda t: (t['cy'], t['x']))
    used = [False] * len(tokens)
    groups: List[Dict] = []

    for i, tok in enumerate(tokens):
        if used[i]:
            continue
        group_text = tok['text']
        gx1 = tok['x']
        gy1 = tok['cy']
        gx2 = tok['x'] + tok['w']
        max_conf = tok['conf']
        best_feat = (tok['feat_x'], tok['feat_y'])

        for j in range(i + 1, len(tokens)):
            if used[j]:
                continue
            other = tokens[j]
            if abs(other['cy'] - gy1) > y_delta:
                break  # sorted by cy — no point continuing
            dx_gap = other['x'] - gx2
            if 0 <= dx_gap <= x_gap:
                group_text += ' ' + other['text']
                gx2 = other['x'] + other['w']
                if other['conf'] > max_conf:
                    max_conf = other['conf']
                    best_feat = (other['feat_x'], other['feat_y'])
                used[j] = True

        groups.append({
            'text':   group_text.strip(),
            'x':      float((gx1 + gx2) / 2.0),
            'w':      float(gx2 - gx1),
            'cy':     float(gy1),
            'feat_x': float(best_feat[0]),
            'feat_y': float(best_feat[1]),
        })

    return groups


def _ocr_full_page(
    gray: np.ndarray,
    lines: List[Tuple],
    contours: List,
    x_min: int, x_max: int,
    y_min: int, y_max: int,
    near_line_dist: int,
) -> List[Dict]:
    """
    Run a SINGLE full-page Tesseract call (psm 11) and return filtered tokens.

    P9 fix: replaces the v1 per-contour pytesseract loop (500+ OS processes).
    """
    scale = 1.5
    upscaled = cv2.resize(
        gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    sharpened = cv2.filter2D(upscaled, -1, kernel)
    thresh = cv2.adaptiveThreshold(
        sharpened, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 31, 5,
    )

    # One Tesseract call for the entire page (psm 11 = sparse text)
    ocr = pytesseract.image_to_data(
        thresh,
        config='--psm 11 --oem 3',
        output_type=pytesseract.Output.DICT,
    )

    tokens: List[Dict] = []
    n = len(ocr['text'])

    for i in range(n):
        text = (ocr['text'][i] or '').strip()
        conf = float(ocr['conf'][i])

        if not text or conf < 0:
            continue

        # Convert upscaled coordinates back to original image space
        ox = int(ocr['left'][i] / scale)
        oy = int(ocr['top'][i] / scale)
        ow = int(ocr['width'][i] / scale)
        oh = int(ocr['height'][i] / scale)
        cx = float(ox + ow / 2.0)
        cy = float(oy + oh / 2.0)

        # Spatial exclusion
        if cx < x_min or cx > x_max:
            continue
        if cy < y_min or cy > y_max:
            continue

        # Hard confidence floor (P7 fix: was 15, now 40)
        if conf < MIN_NEAR_LINE_CONF:
            continue

        is_eng = bool(re.search(r'[Øøø∅RrMmHh°±\d\.\+\-/]', text))

        # Medium-confidence tokens: only if engineering text near a dim line
        if conf < MIN_OCR_CONF:
            if not is_eng:
                continue
            near = False
            for lx1, ly1, lx2, ly2 in lines:
                dx = lx2 - lx1
                dy = ly2 - ly1
                if dx == 0 and dy == 0:
                    d = math.hypot(cx - lx1, cy - ly1)
                else:
                    t_val = max(0.0, min(1.0,
                        ((cx - lx1) * dx + (cy - ly1) * dy) / (dx * dx + dy * dy)))
                    d = math.hypot(
                        cx - (lx1 + t_val * dx),
                        cy - (ly1 + t_val * dy),
                    )
                if d < near_line_dist:
                    near = True
                    break
            if not near:
                continue

        feat_x, feat_y = _find_nearest_feature(cx, cy, lines, contours)

        tokens.append({
            'text':   text,
            'x':      ox,
            'w':      ow,
            'cy':     cy,
            'conf':   conf,
            'feat_x': float(feat_x),
            'feat_y': float(feat_y),
        })

    return tokens


# ─── Public OCR entry point ───────────────────────────────────────────────────

def detect_annotations(image: np.ndarray) -> List[Dict[str, Any]]:
    """
    Detect CAD annotation text from a BGR page image (OCR fallback path).
    Always returns a list — never None.
    """
    if image is None or image.size == 0:
        return []
    try:
        return _detect_ocr_impl(image)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error(
            'detect_annotations failed: %s', exc, exc_info=True)
        return []


def _detect_ocr_impl(image: np.ndarray) -> List[Dict[str, Any]]:
    """Core OCR detection logic."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    img_h, img_w = gray.shape

    scale_ratio = img_h / 1200.0
    group_y_delta  = int(max(6,  GROUP_Y_DELTA  * scale_ratio))
    group_x_gap    = int(max(15, GROUP_X_GAP    * scale_ratio))
    dedup_radius   = int(max(15, DEDUP_RADIUS   * scale_ratio))
    near_line_dist = int(max(30, NEAR_LINE_DIST * scale_ratio))

    # Exclusion zones (P5 fix: TITLE_BLOCK_FRAC = 0.78 for all orientations)
    y_min = int(img_h * BORDER_FRAC_Y)
    y_max = int(img_h * TITLE_BLOCK_FRAC)
    x_min = int(img_w * BORDER_FRAC_X)
    x_max = int(img_w * (1.0 - BORDER_FRAC_X))

    # Structural features
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    raw_lines = cv2.HoughLinesP(
        edges, rho=1, theta=np.pi / 180,
        threshold=60, minLineLength=40, maxLineGap=10,
    )
    lines: List[Tuple] = []
    if raw_lines is not None:
        for ln in raw_lines:
            lines.append(tuple(int(v) for v in ln[0]))

    _, thresh_full = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    cnts, _ = cv2.findContours(
        thresh_full, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)  # P1 fix: RETR_LIST
    contours = [
        c for c in cnts
        if 200 < cv2.contourArea(c) < img_w * img_h * 0.04
    ]

    # Single full-page OCR call (P9 fix: replaces per-contour loop)
    raw_tokens = _ocr_full_page(
        gray, lines, contours,
        x_min, x_max, y_min, y_max,
        near_line_dist,
    )

    # Group adjacent tokens on the same line
    grouped = _group_tokens(raw_tokens, y_delta=group_y_delta, x_gap=group_x_gap)

    # Classify, clean, parse structured fields
    classified: List[Dict] = []
    for g in grouped:
        clean_text = _CLEAN_PREFIX.sub('', g['text']).strip()
        clean_text = _correct_ocr_text(clean_text)
        if not clean_text:
            continue
        if _TITLE_BLOCK_REJECT.search(clean_text):
            continue
        # OCR path: require engineering patterns (require_engineering=True)
        ann_type = _classify_text_strict(clean_text, require_engineering=True)
        if ann_type is None:
            continue
        fields = _parse_annotation_fields(clean_text, ann_type)
        classified.append({
            'text':      clean_text,
            'type':      ann_type,
            'x':         round(float(g['x']), 1),
            'y':         round(float(g['cy']), 1),
            'feature_x': round(float(g['feat_x']), 1),
            'feature_y': round(float(g['feat_y']), 1),
            **fields,
        })

    return _deduplicate(classified, radius=dedup_radius)
