# Changelog

All notable changes to CADLens, condensed from version history in the original README.

---

## v2.2 — AS9102 Form 3 Compliance, Spatial Numbering, and Selective Export

- Added `upper_limit`, `lower_limit`, `char_designator`, and `inspection_tool` fields to data models, sidebar editor, and Excel export to conform with AS9102 Form 3 First Article Inspection standards.
- Added `_calculate_limits` in `detector.py` to automatically compute Upper Limit (Max) and Lower Limit (Min) from nominal and bilateral/unilateral tolerances.
- Implemented spatial band sorting in `balloon_manager.py`: annotations are grouped into 150 px horizontal bands and numbered top-to-bottom, left-to-right.
- Added `_pick_best_balloon_position` to score eight candidate direction vectors and select the initial balloon placement that minimises collisions and border proximity.
- Added feature clearance repulsion (28 px minimum) in `spread_overlapping_balloons` to prevent balloon badges from obscuring the dimension value text.
- Added `_detect_title_block_bounds` to dynamically locate the title block via keyword anchors rather than relying solely on a fixed y-coordinate cutoff.
- Added `POST /export/{id}/selected` endpoint and `?balloon_ids=` query parameter support on `GET /export/{id}` for selective balloon export.
- Added multi-select checkboxes, Select All, designator badges, and inspection tool dropdown to the sidebar.

---

## v2.1 — Interactive Ballooning and CAD Precision Tolerancing

- Added two-way canvas–sidebar synchronization: clicking a balloon on the canvas auto-expands and scrolls to the matching sidebar row, and vice versa.
- Fixed leader line drag: dragging the balloon badge now moves only the badge `(x, y)` and keeps the leader tip `(feature_x, feature_y)` pinned to the CAD feature.
- Fixed drag state management: `mouseup` listener moved to `window` level so releasing the mouse outside the canvas always terminates the drag.
- Implemented `_extract_stacked_tolerances` with y-proximity clustering to correctly extract upper (`+0.039`) and lower (`-0.000`) deviations from multi-line stacked tolerance callouts.
- Added `_DEGREE_FIXUP` to normalize MacRoman/Windows-1252 degree symbol variants (`\x83`, `\xb0`) before parsing; chamfers like `1x45°` now classify as Dimension with process `CHAMFER`.
- Fixed ISO fit classification (`H8`, `H11`, `H12`): fits are now parsed into `tolerance_zone` and no longer cause early return in the field parser.
- Completed export integration for nominal values, upper/lower tolerances, ISO fits, and machining processes.

---

## v2.0 — Hybrid Detection Engine

- Added `detect_from_pdf_page` as the primary detection path: reads native vector text from PyMuPDF (`page.get_text('words')`) with no image processing overhead.
- Replaced per-contour Tesseract loop (which spawned 500+ OS processes) with a single full-page Tesseract call (`--psm 11`), reducing per-page processing time significantly.
- Tightened classification: `_DIM_PATTERNS` regex requires engineering-specific prefixes (Ø, R, M, H, °, mm, decimal). Previously any text containing a digit was classified as a Dimension.
- Fixed title block exclusion for all drawing orientations: `TITLE_BLOCK_FRAC` set to 0.78, was effectively disabled for landscape drawings.
- Raised OCR confidence thresholds: hard floor 40 (was 15), pass threshold 50 (was 45).
- Added `_parse_annotation_fields`: structured field parsing populating `nominal_value`, `tolerance_upper`, `tolerance_lower`, `surface_finish`, `datum_ref`, `tolerance_zone`, `quantity`, `material` automatically.
- Fixed `import pymupdf` (replaces deprecated `import fitz`).
- Fixed RGBA 4-channel PDF renders crashing `cv2.COLOR_BGR2GRAY`.
- Fixed YOLO balloon coordinates: previously scaled to a 1000 px thumbnail; now use native image coordinates.
- Fixed manual balloon add: `balloon_no` now uses `max(balloon_no) + 1` instead of `count + 1` to avoid duplicate numbers after a delete.
- Fixed sidebar stale data: `useEffect` in `DetailField` now syncs when the selected balloon changes.
- Added balloon drag and drop (badge and leader tip).
- Replaced blocking `window.confirm()` delete dialog with a styled in-app confirmation dialog.
- Centralized API base URL in `src/api.js` (was hardcoded in multiple files).
- Added `frontend/.env.example` for new contributors.
