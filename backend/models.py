from pydantic import BaseModel
from typing import List, Optional

class ProjectParameters(BaseModel):
    carrier_width: float = 38.0
    carrier_deck_length: float = 63.0
    deck_height: float = 17.0
    ramp_length: float = 61.0
    ramp_clearance: float = 1.0
    receiver_spacing: float = 38.0
    receiver_height: float = 17.0
    machine_width: float = 36.0
    machine_length: float = 70.5
    machine_weight: float = 698.0
    flared_guide_height: float = 3.0
    flare_angle: float = 45.0
    flare_width: float = 1.5

class MaterialShape(BaseModel):
    name: str
    type: str
    width: float
    height: float
    thickness: float
    grade: str
    unit_weight: float

class BomRow(BaseModel):
    mark: str
    description: str
    material: str
    section: str
    grade: str
    cut_length: float
    quantity: int
    unit_weight: float
    total_weight: float

class CutListRow(BaseModel):
    mark: str
    raw_section: str
    cut_length: float
    quantity: int
    cut_notes: str

class PurchaseRow(BaseModel):
    section: str
    stick_length: float
    quantity: int

class ProjectData(BaseModel):
    id: str = "default"
    name: str = "Z Spray Carrier"
    parameters: ProjectParameters = ProjectParameters()

