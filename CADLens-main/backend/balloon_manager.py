import math
from typing import List, Dict, Any


def assign_balloon_numbers(
    detections: List[Dict[str, Any]],
    document_id: str,
    page: int,
    start_no: int = 1,
) -> List[Dict[str, Any]]:
    """
    Convert raw detector detections into balloon dicts with sequential numbers.

    Args:
        detections:   list of {text, type, x, y, feature_x, feature_y}
        document_id:  MongoDB document ID string
        page:         1-based page number
        start_no:     first balloon number to assign (useful for multi-page)

    Returns:
        list of balloon dicts ready for MongoDB insertion
    """
    balloons = []
    for idx, det in enumerate(detections):
        balloon = {
            "document_id": document_id,
            "balloon_no": start_no + idx,
            "text": str(det.get("text", "")),
            "type": str(det.get("type", "Note")),
            # Explicit float() — OpenCV returns np.int32/np.float32 which pymongo rejects
            "x": float(det.get("x", 0.0)),
            "y": float(det.get("y", 0.0)),
            "feature_x": float(det.get("feature_x", det.get("x", 0.0))),
            "feature_y": float(det.get("feature_y", det.get("y", 0.0))),
            "page": int(page),
            "description": "",
            "remarks": "",
        }
        balloons.append(balloon)
    return balloons


def spread_overlapping_balloons(
    balloons: List[Dict[str, Any]],
    min_distance: float = 40.0,
    max_iterations: int = 100,
) -> List[Dict[str, Any]]:
    """
    If two balloons are closer than min_distance pixels, offset one so they
    don't overlap visually.  Uses a simple iterative repulsion approach.

    Modifies x, y in-place and returns the same list.
    """
    for _ in range(max_iterations):
        moved = False
        for i in range(len(balloons)):
            for j in range(i + 1, len(balloons)):
                b1 = balloons[i]
                b2 = balloons[j]
                dx = b2["x"] - b1["x"]
                dy = b2["y"] - b1["y"]
                dist = math.hypot(dx, dy)
                if dist < min_distance and dist > 0:
                    # Push b2 away from b1
                    overlap = (min_distance - dist) / 2.0
                    nx = dx / dist
                    ny = dy / dist
                    b1["x"] = float(b1["x"] - nx * overlap)
                    b1["y"] = float(b1["y"] - ny * overlap)
                    b2["x"] = float(b2["x"] + nx * overlap)
                    b2["y"] = float(b2["y"] + ny * overlap)
                    moved = True
                elif dist == 0:
                    # Exactly same position — nudge b2 diagonally
                    b2["x"] = float(b2["x"] + min_distance)
                    b2["y"] = float(b2["y"] + min_distance)
                    moved = True
        if not moved:
            break

    return balloons
