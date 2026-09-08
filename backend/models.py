from enum import Enum
from typing import List, Dict, Optional, Any, Tuple
from pydantic import BaseModel, Field

class StatusEnum(str, Enum):
    MEASURED = "MEASURED"
    OEM = "OEM"
    DESIGN = "DESIGN"
    CALCULATED = "CALCULATED"
    ESTIMATED_UNVERIFIED = "ESTIMATED_UNVERIFIED"

class ParameterItem(BaseModel):
    name: str
    value: float
    units: str = "in"
    status: StatusEnum = StatusEnum.DESIGN
    description: str = ""
    source_note: str = ""
    required_before_fabrication: bool = False

class ProjectParameters(BaseModel):
    # Carrier Geometry
    carrier_width: float = 38.00               # MEASURED: Outside frame width (in)
    carrier_deck_length: float = 63.00        # MEASURED: Front stop to ramp hinge CL (in)
    deck_height: float = 17.00                # DESIGN/MEASURED: Target deck height above ground (in)
    
    # Wheel Track Geometry
    track_flat_width: float = 12.00           # DESIGN: Width of each wheel track (in)
    track_outer_spacing: float = 38.00        # CALCULATED/DESIGN: Outside-to-outside of tracks (in)
    track_center_gap: float = 14.00           # CALCULATED: Clear opening between tracks (in)
    flared_guide_height: float = 3.00         # DESIGN: Vertical guide height (in)
    flare_angle: float = 45.0                 # DESIGN: Outward flare angle (degrees)
    flare_width: float = 1.50                 # DESIGN: Flare horizontal projection (in)
    
    # Ramp Geometry (One rigid hinged assembly)
    ramp_length: float = 61.00                # MEASURED: Hinge CL to tip (in)
    ramp_clearance: float = 1.00              # DESIGN: Nominal clearance behind rear tires to ramp (in)
    ramp_hinge_pin_dia: float = 0.75          # DESIGN: Hinge pin diameter (in)
    ramp_hinge_sleeve_wall: float = 0.188     # DESIGN: Hinge sleeve wall thickness (in)
    
    # Truck Interface
    receiver_spacing: float = 38.00           # MEASURED: Center-to-center span (in)
    receiver_outside_span: float = 40.00      # MEASURED: Outside-to-outside span (in)
    receiver_tube_width: float = 2.00         # MEASURED: Outside width of receiver tube (in)
    stinger_section: str = "2x2x1/4 Tube"      # DESIGN: Structural tube for stingers
    stinger_insertion_length: float = 18.00   # ESTIMATED_UNVERIFIED: Penetration into truck receiver (in)
    stinger_overlap_length: float = 14.00     # DESIGN: Welded underframe overlap length (in)
    hitch_pin_hole_setback: float = 3.00      # ESTIMATED_UNVERIFIED: Pin hole from stinger tip (in)
    hitch_pin_hole_dia: float = 0.656         # DESIGN: 5/8" hitch pin hole diameter (+1/32" clearance) (in)
    truck_suspension_drop: float = 1.50       # ESTIMATED_UNVERIFIED: Anticipated squat under payload (in)
    
    # Machine Specifications (2026 Z-Spray Junior ZSX3624)
    machine_width: float = 36.00              # OEM: Machine overall width (in)
    machine_length_oem: float = 70.50         # OEM: Machine nominal length (in)
    machine_length_field: float = 72.00       # MEASURED: Practical field length (in)
    machine_height: float = 48.00             # OEM: Height (in)
    machine_curb_weight: float = 698.0        # OEM: Dry curb weight (lb)
    fertilizer_hopper_weight: float = 150.0   # OEM: Main hopper capacity (lb)
    fertilizer_trays_weight: float = 100.0    # OEM: Two 50 lb trays (lb)
    spray_tank_gallons: float = 24.0          # OEM: Spray liquid capacity (gal)
    liquid_density_lb_gal: float = 8.34       # Water/liquid chemical density (lb/gal)
    
    # Engineering / Structural Factors
    vertical_dynamic_factor: float = 2.00     # DESIGN: Rough road bump factor (g)
    braking_factor: float = 0.80              # DESIGN: Deceleration factor (g)
    lateral_factor: float = 0.50              # DESIGN: Cornering factor (g)
    material_yield_strength: float = 46000.0  # A500 Gr B yield strength (psi)
    target_safety_factor: float = 2.00        # Minimum desired safety factor
    
    # Stock Cutting Preferences
    available_stock_lengths: List[float] = [240.0, 288.0] # 20 ft and 24 ft
    saw_kerf: float = 0.125                   # 1/8" saw kerf

class Point3D(BaseModel):
    x: float
    y: float
    z: float

class Hole(BaseModel):
    diameter: float
    center_x: float
    center_y: float
    center_z: float = 0.0
    reference_datum: str = "FRONT_DATUM"
    note: str = ""
    status: StatusEnum = StatusEnum.DESIGN

class Weld(BaseModel):
    connected_pieces: List[str]
    weld_type: str = "FILLET" # FILLET, GROOVE, PLUG
    size: str = "3/16"
    length: Optional[float] = None
    all_around: bool = False
    shop_note: str = ""
    status: StatusEnum = StatusEnum.DESIGN

class Member(BaseModel):
    piece_mark: str
    description: str
    section: str
    grade: str = "ASTM A500 Gr B"
    length: float
    quantity: int = 1
    start_pt: Point3D
    end_pt: Point3D
    orientation: str = "X" # X (longitudinal), Y (transverse), Z (vertical)
    assembly: str = "MAIN_CARRIER" # MAIN_CARRIER, RAMP, STINGER, DETAILS
    cut_type: str = "SQUARE" # SQUARE, MITER_45, BEVEL
    cut_angle_left: float = 0.0
    cut_angle_right: float = 0.0
    unit_weight: float # lb/ft
    total_weight: float # lb
    notes: str = ""
    status: StatusEnum = StatusEnum.DESIGN

class Plate(BaseModel):
    piece_mark: str
    description: str
    thickness: float
    width: float
    length: float
    profile_pts: List[Tuple[float, float]] = []
    holes: List[Hole] = []
    grade: str = "ASTM A36"
    material: str = "Steel Plate"
    quantity: int = 1
    unit_weight: float # lb/plate
    total_weight: float # lb
    assembly: str = "MAIN_CARRIER"
    cut_notes: str = "Shear / Waterjet / Plasma cut"
    status: StatusEnum = StatusEnum.DESIGN

class HingeComponent(BaseModel):
    pin_diameter: float = 0.75
    pin_length: float = 40.00
    sleeve_od: float = 1.125
    sleeve_id: float = 0.781
    sleeve_lengths: List[float] = [3.0, 3.0, 3.0, 3.0]
    pin_material: str = "AISI 1018 Cold Finished Round"
    sleeve_material: str = "ASTM A513 DOM Mechanical Tube"
    retaining_method: str = "Cross-drilled 3/16\" Hole for Linch Pin with 3/4\" Heavy Flat Washers"
    status: StatusEnum = StatusEnum.DESIGN

class StructuralCheckResult(BaseModel):
    payload_weight: float
    carrier_dead_weight: float
    total_suspended_weight: float
    dynamic_vertical_load: float
    dynamic_moment_in_lb: float
    stinger_reaction_force_lb: float
    stinger_bending_stress_psi: float
    yield_strength_psi: float
    factor_of_safety: float
    is_adequate: bool
    notes: List[str] = []

class BomRow(BaseModel):
    piece_mark: str
    description: str
    assembly: str
    shape: str
    size: str
    grade: str
    cut_length: float
    quantity: int
    unit_weight: float # lb/ft or lb/ea
    total_weight: float # lb
    notes: str = ""

class CutListRow(BaseModel):
    piece_mark: str
    section: str
    cut_length: float
    quantity: int
    cut_type: str = "SQUARE"
    cut_angle_left: float = 0.0
    cut_angle_right: float = 0.0
    notes: str = ""

class PurchaseRow(BaseModel):
    section: str
    grade: str
    stick_length: float
    quantity: int
    total_purchased_length: float
    total_purchased_weight: float

class StockStick(BaseModel):
    stick_id: str
    section: str
    grade: str
    stock_length: float
    parts: List[Dict[str, Any]]
    total_used: float
    kerf_used: float
    scrap_remaining: float
    efficiency_pct: float

class StockPlanResult(BaseModel):
    stock_plan: List[StockStick]
    purchase_list: List[PurchaseRow]
    total_purchased_weight: float
    total_cut_weight: float
    overall_efficiency_pct: float

class ProjectData(BaseModel):
    id: str = "default"
    name: str = "Z Spray Carrier"
    parameters: ProjectParameters = ProjectParameters()
    provenance: Dict[str, ParameterItem] = {}
