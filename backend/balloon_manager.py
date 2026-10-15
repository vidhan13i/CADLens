import math
from typing import List, Dict, Any, Tuple


# Candidate direction offsets (dx, dy) for smart initial balloon placement
CANDIDATE_OFFSETS: List[Tuple[float, float]] = [
    (65.0, -55.0),   # North-East (standard engineering drawing preference)
    (-65.0, -55.0),  # North-West
    (65.0, 55.0),    # South-East
    (-65.0, 55.0),   # South-West
    (0.0, -70.0),    # North
    (0.0, 70.0),     # South
    (75.0, 0.0),     # East
    (-75.0, 0.0),    # West
]


def _pick_best_balloon_position(
    fx: float,
    fy: float,
    placed_balloons: List[Dict[str, float]],
    page_w: float = 0.0,
    page_h: float = 0.0,
) -> Tuple[float, float]:
    """
    Select the optimal (x, y) balloon position around a feature point (fx, fy).
    Balances margin clearance, distance from already placed balloons, and clean leader geometry.
    """
    best_pos = (fx + 65.0, fy - 55.0)
    best_penalty = float("inf")

    margin = 50.0

    for dx, dy in CANDIDATE_OFFSETS:
        bx = fx + dx
        by = fy + dy
        penalty = 0.0

        # Boundary checks
        if page_w > 0:
            if bx < margin:
                penalty += (margin - bx) * 10.0
            elif bx > page_w - margin:
                penalty += (bx - (page_w - margin)) * 10.0

        if page_h > 0:
            if by < margin:
                penalty += (margin - by) * 10.0
            elif by > page_h - margin:
                penalty += (by - (page_h - margin)) * 10.0

        # Proximity to already placed balloons
        for pb in placed_balloons:
            dist = math.hypot(bx - pb["x"], by - pb["y"])
            if dist < 45.0:
                penalty += (45.0 - dist) * 15.0

        # Preference penalty (prefer NE / NW diagonal placements)
        if dx > 0 and dy < 0:
            penalty += 0.0       # NE preferred
        elif dx < 0 and dy < 0:
            penalty += 5.0       # NW second
        else:
            penalty += 15.0

        if penalty < best_penalty:
            best_penalty = penalty
            best_pos = (bx, by)

    return best_pos


def assign_balloon_numbers(
    detections: List[Dict[str, Any]],
    document_id: str,
    page: int,
    start_no: int = 1,
    page_width: float = 0.0,
    page_height: float = 0.0,
) -> List[Dict[str, Any]]:
    """
    Convert raw detector detections into balloon dicts with sequential numbers.
    Follows industrial FAI / AS9102 inspection standards:
      1. Spatial Sorting: Top-to-Bottom, Left-to-Right reading flow across visual bands.
      2. Non-Colliding Initial Placement: Picks optimal clear direction.
      3. Structured Fields: Preserves nominals, tolerances, calculated limits, and tools.
    """
    # Group into visual horizontal bands of height ~150px, then sort left-to-right (x ascending)
    band_height = 150.0
    sorted_detections = sorted(
        detections,
        key=lambda d: (
            round(float(d.get("feature_y", d.get("y", 0.0))) / band_height) * band_height,
            float(d.get("feature_x", d.get("x", 0.0))),
        ),
    )

    balloons = []
    placed_positions: List[Dict[str, float]] = []

    for idx, det in enumerate(sorted_detections):
        fx = float(det.get("feature_x", det.get("x", 0.0)))
        fy = float(det.get("feature_y", det.get("y", 0.0)))

        # If detection already specifies an optimized (x, y), use it; otherwise pick best direction
        raw_x = det.get("x")
        raw_y = det.get("y")
        if raw_x is not None and raw_y is not None and (raw_x != fx or raw_y != fy):
            bx, by = float(raw_x), float(raw_y)
        else:
            bx, by = _pick_best_balloon_position(fx, fy, placed_positions, page_width, page_height)

        placed_positions.append({"x": bx, "y": by})

        balloon = {
            "document_id": document_id,
            "balloon_no": start_no + idx,
            "text": str(det.get("text", "")),
            "type": str(det.get("type", "Note")),
            "x": float(bx),
            "y": float(by),
            "feature_x": float(fx),
            "feature_y": float(fy),
            "page": int(page),
            "nominal_value":   str(det.get("nominal_value",   "")),
            "units":           str(det.get("units", "mm" if det.get("type") in ("Dimension", "Linear", "Diameter", "Radius", "Angle") else "")),
            "tolerance_upper": str(det.get("tolerance_upper", "")),
            "tolerance_lower": str(det.get("tolerance_lower", "")),
            "upper_limit":     str(det.get("upper_limit",     "")),
            "lower_limit":     str(det.get("lower_limit",     "")),
            "char_designator": str(det.get("char_designator", "Standard")),
            "inspection_tool": str(det.get("inspection_tool", "")),
            "surface_finish":  str(det.get("surface_finish",  "")),
            "process":         str(det.get("process",         "")),
            "datum_ref":       str(det.get("datum_ref",       "")),
            "tolerance_zone":  str(det.get("tolerance_zone",  "")),
            "quantity":        str(det.get("quantity",        "")),
            "material":        str(det.get("material",        "")),
            "description":     str(det.get("description",     "")),
            "remarks":         str(det.get("remarks",         "")),
        }
        balloons.append(balloon)

    return balloons


def spread_overlapping_balloons(
    balloons: List[Dict[str, Any]],
    min_distance: float = 42.0,
    max_iterations: int = 120,
    page_width: float = 0.0,
    page_height: float = 0.0,
) -> List[Dict[str, Any]]:
    """
    Repulsion physics simulation:
      1. Pushes apart overlapping balloons (dist < min_distance).
      2. Ensures balloons maintain clearance from feature text point so the circle badge never covers numbers.
      3. Clamps positions within page bounds if dimensions are given.
    """
    margin = 35.0

    for _ in range(max_iterations):
        moved = False
        for i in range(len(balloons)):
            b1 = balloons[i]

            # 1. Repel from feature point if too close (avoid obscuring dimension digits)
            dfx = b1["x"] - b1["feature_x"]
            dfy = b1["y"] - b1["feature_y"]
            feat_dist = math.hypot(dfx, dfy)
            min_feat_clearance = 28.0
            if feat_dist < min_feat_clearance:
                if feat_dist > 0:
                    push = (min_feat_clearance - feat_dist)
                    b1["x"] += (dfx / feat_dist) * push
                    b1["y"] += (dfy / feat_dist) * push
                else:
                    b1["x"] += min_feat_clearance
                    b1["y"] -= min_feat_clearance
                moved = True

            # 2. Pairwise balloon repulsion
            for j in range(i + 1, len(balloons)):
                b2 = balloons[j]
                dx = b2["x"] - b1["x"]
                dy = b2["y"] - b1["y"]
                dist = math.hypot(dx, dy)

                if 0 < dist < min_distance:
                    overlap = (min_distance - dist) / 2.0
                    nx = dx / dist
                    ny = dy / dist
                    b1["x"] = float(b1["x"] - nx * overlap)
                    b1["y"] = float(b1["y"] - ny * overlap)
                    b2["x"] = float(b2["x"] + nx * overlap)
                    b2["y"] = float(b2["y"] + ny * overlap)
                    moved = True
                elif dist == 0:
                    b2["x"] = float(b2["x"] + min_distance)
                    b2["y"] = float(b2["y"] + min_distance)
                    moved = True

            # 3. Canvas boundary clamping
            if page_width > 0:
                b1["x"] = max(margin, min(page_width - margin, b1["x"]))
            if page_height > 0:
                b1["y"] = max(margin, min(page_height - margin, b1["y"]))

        if not moved:
            break

    # Final clamping pass for all balloons
    if page_width > 0 or page_height > 0:
        for b in balloons:
            if page_width > 0:
                b["x"] = max(margin, min(page_width - margin, b["x"]))
            if page_height > 0:
                b["y"] = max(margin, min(page_height - margin, b["y"]))

    return balloons
