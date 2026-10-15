from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Document(BaseModel):
    id: Optional[str] = None
    filename: str
    file_path: str
    upload_time: datetime = Field(default_factory=datetime.utcnow)
    page_count: int


class Balloon(BaseModel):
    id: Optional[str] = None
    document_id: str
    balloon_no: int
    text: str
    type: str               # Dimension | Tolerance | Surface Finish | GD&T | Note | balloon
    x: float
    y: float
    feature_x: float
    feature_y: float
    page: int

    # ── Common fields ─────────────────────────────────────────────────────────
    description:     Optional[str] = ""
    remarks:         Optional[str] = ""

    # ── Dimension & AS9102 Inspection fields ──────────────────────────────────
    nominal_value:   Optional[str] = ""   # e.g. "39", "100"
    units:           Optional[str] = ""   # e.g. "mm", "°", "in"
    tolerance_upper: Optional[str] = ""   # e.g. "+0.039"
    tolerance_lower: Optional[str] = ""   # e.g. "-0.000"
    upper_limit:     Optional[str] = ""   # e.g. "39.039" (calculated / Form 3)
    lower_limit:     Optional[str] = ""   # e.g. "39.000" (calculated / Form 3)
    char_designator: Optional[str] = ""   # Standard | Critical | Major | Reference | Basic
    inspection_tool: Optional[str] = ""   # e.g. Caliper, Micrometer, CMM, Thread Gauge
    surface_finish:  Optional[str] = ""   # e.g. "Ra 1.6"
    process:         Optional[str] = ""   # e.g. "Drilling", "Turning"

    # ── GD&T-specific ────────────────────────────────────────────────────────
    datum_ref:       Optional[str] = ""   # e.g. "A", "A-B"
    tolerance_zone:  Optional[str] = ""   # e.g. "0.05", "Ø0.1"

    # ── General / Note-specific ───────────────────────────────────────────────
    quantity:        Optional[str] = ""   # e.g. "62 Nos.", "4X"
    material:        Optional[str] = ""   # e.g. "C45 Steel"


class BalloonCreate(BaseModel):
    document_id: str
    x: float
    y: float
    feature_x: float
    feature_y: float
    page: int
    text: str
    type: str
    units: Optional[str] = "mm"
    nominal_value:   Optional[str] = ""
    tolerance_upper: Optional[str] = ""
    tolerance_lower: Optional[str] = ""
    upper_limit:     Optional[str] = ""
    lower_limit:     Optional[str] = ""
    char_designator: Optional[str] = ""
    inspection_tool: Optional[str] = ""
    quantity:        Optional[str] = ""


class BalloonUpdate(BaseModel):
    # Editable meta
    text:            Optional[str] = None
    type:            Optional[str] = None

    # Common
    description:     Optional[str] = None
    remarks:         Optional[str] = None

    # Dimension & AS9102 inspection
    nominal_value:   Optional[str] = None
    units:           Optional[str] = None
    tolerance_upper: Optional[str] = None
    tolerance_lower: Optional[str] = None
    upper_limit:     Optional[str] = None
    lower_limit:     Optional[str] = None
    char_designator: Optional[str] = None
    inspection_tool: Optional[str] = None
    surface_finish:  Optional[str] = None
    process:         Optional[str] = None

    # GD&T
    datum_ref:       Optional[str] = None
    tolerance_zone:  Optional[str] = None

    # General
    quantity:        Optional[str] = None
    material:        Optional[str] = None
