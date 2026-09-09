from enum import Enum
from typing import List, Dict, Optional, Any, Tuple
from pydantic import BaseModel, Field

class StatusEnum(str, Enum):
    MEASURED = "MEASURED"
    OEM = "OEM"
    DESIGN = "DESIGN"
    CALCULATED = "CALCULATED"
    ESTIMATED_UNVERIFIED = "ESTIMATED_UNVERIFIED"
    # Established on the truck / with the machine during ordinary fit-up.
    # Never printed as a shop dimension.
    FIELD_FIT = "FIELD_FIT"
    # A coordinate the program needs to draw the model. NOT a shop dimension.
    MODEL_ONLY = "MODEL_ONLY"


# Shop-facing wording for the two statuses that must never look like a
# production dimension.
FIELD_FIT_TEXT = "FIELD FIT TO TRUCK"
FIT_UP_TEXT = "CHECK DURING MACHINE FIT-UP"

class ParameterItem(BaseModel):
    name: str
    value: float
    units: str = "in"
    status: StatusEnum = StatusEnum.DESIGN
    description: str = ""
    source_note: str = ""
    required_before_fabrication: bool = False

class ProjectParameters(BaseModel):
    # Carrier Maximum Envelope & Base Geometry
    carrier_max_overall_width: float = 38.00  # HARD REQUIREMENT: Max outside width of completed carrier including flare tips (in)
    carrier_width: float = 36.00              # Frame outside width (in) = carrier_max_overall_width - 2 * flare_width
    carrier_deck_length: float = 63.00        # MEASURED: Deck frame length, front face to rear face (in)
    deck_height: float = 17.25                # DESIGN: Running deck height above ground (in) - approx 17"
    
    # Wheel Track Geometry
    track_flat_width: float = 11.50           # DESIGN: Width of each flat wheel track (in)
    track_outer_spacing: float = 36.00        # CALCULATED: Outside-to-outside of track frame (in)
    track_center_gap: float = 13.00           # CALCULATED: Clear cleanout opening between tracks (in)
    flared_guide_height: float = 3.00         # DESIGN: Vertical guide height (in)
    flare_angle: float = 45.0                 # DESIGN: Outward flare angle (degrees)
    flare_width: float = 1.00                 # DESIGN: Flare horizontal projection per side (in) (36.0 + 2*1.0 = 38.00" MAX)
    
    # Ramp Geometry (One rigid hinged assembly)
    ramp_length: float = 61.00                # MEASURED: Hinge CL to tip (in)
    ramp_clearance: float = 1.00              # FIELD_FIT: Nominal clearance behind rear tires to ramp (in)

    # Ramp Hinge - ordinary welded barrel hinge on one continuous pin.
    # The gap between the deck and the ramp IS the barrel OD, so every barrel
    # sits tangent in the corner of its own crossmember. Nothing is machined.
    hinge_pin_dia: float = 0.750              # DESIGN: 3/4" cold-finished round bar pin
    hinge_barrel_od: float = 1.250            # DESIGN: 1-1/4" OD barrel stock
    hinge_barrel_wall: float = 0.1875         # DESIGN: 3/16" wall
    hinge_barrel_id: float = 0.875            # DESIGN: 7/8" bore -> 1/8" running clearance on the pin
    hinge_barrel_length: float = 4.00         # DESIGN: Each barrel 4" long
    hinge_barrel_count: int = 7               # DESIGN: 4 carrier + 3 ramp, interleaved, symmetric
    hinge_barrel_gap: float = 0.50            # DESIGN: Clear gap between adjacent barrels
    hinge_pin_length: float = 36.00           # DESIGN: Pin length (in)

    # Truck Interface.
    # There is no receiver-socket survey here on purpose. The two stingers are
    # located by sliding them into the two existing sockets; the truck is the
    # fixture. The one spacing value below exists only so the program can draw
    # the model and is never printed as a shop dimension.
    stinger_spacing_model_nominal: float = 37.50  # MODEL_ONLY: drawing coordinate, NOT a shop dimension
    stinger_section: str = "2x2x1/4 Tube"      # DESIGN: Structural tube for stingers
    stinger_sleeve_section: str = "2.5x2.5x3/16 Tube"  # DESIGN: Slip-over reinforcement, outside the socket
    stinger_sleeve_length: float = 40.00      # DESIGN: Sleeve length (in), front end field fit to socket face
    stinger_insertion_length: float = 18.00   # FIELD_FIT: Nominal penetration into truck receiver (in)
    stinger_overlap_length: float = 40.00     # DESIGN: Length aft of the deck front face (in)
    hitch_pin_hole_setback: float = 3.00      # FIELD_FIT: Nominal; transfer the hole from the truck
    hitch_pin_hole_dia: float = 0.656         # DESIGN: 5/8" hitch pin hole diameter (+1/32" clearance) (in)
    truck_suspension_drop: float = 1.50       # FIELD_FIT: Anticipated squat under payload (in)
    # Under-deck mount beams. Lengths are cut to fit between the two stingers.
    mount_beam_section: str = "2x2x1/4 Tube"  # DESIGN
    mount_beam_stations: List[float] = [4.0, 17.0, 37.0]  # DESIGN: front face X of MB1/MB2/MB3
    
    # Machine Specifications (2026 Z-Spray Junior ZSX3624)
    machine_width: float = 36.00              # OEM: Machine overall width (in)
    machine_length_oem: float = 70.50         # OEM: Machine nominal length (in)
    machine_length_field: float = 72.00       # MEASURED: Practical field length (in)
    machine_height: float = 48.00             # OEM: Height (in)
    machine_rear_tire_size: str = "22x8.5-12" # OEM: Rear tire designation
    machine_front_tire_size: str = "15x6-6"   # OEM: Front tire designation
    machine_rear_tire_width: float = 8.50     # OEM: Rear tire section width (in)
    machine_rear_tire_diameter: float = 22.00 # OEM: Rear tire overall diameter (in)
    machine_front_tire_width: float = 6.00    # OEM: Front tire section width (in)
    machine_front_tire_diameter: float = 15.00 # OEM: Front tire overall diameter (in)
    # Wheel positions are deliberately NOT parameters. Where the machine ends up
    # on the deck is settled by rolling it on during fit-up, not by a survey.
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
    # Acceptance rule: nothing yields at the dynamic bump factor above. That is
    # the same as a factor of 2.0 against yield on the static load. We do NOT
    # stack another safety factor on top of an already-factored load.
    target_safety_factor: float = 2.00        # Static factor against yield
    machine_cg_from_deck_front: float = 31.5  # DESIGN: assumed load position, mid-deck (in)
    
    # Stock Cutting Preferences
    available_stock_lengths: List[float] = [240.0, 288.0] # 20 ft and 24 ft
    saw_kerf: float = 0.125                   # 1/8" saw kerf

class Point3D(BaseModel):
    x: float
    y: float
    z: float

class BoxBounds(BaseModel):
    """Real outside envelope of a fabricated part, in project coordinates."""
    min_x: float = 0.0
    max_x: float = 0.0
    min_y: float = 0.0
    max_y: float = 0.0
    min_z: float = 0.0
    max_z: float = 0.0

class Hole(BaseModel):
    """A hole is a real fabrication feature, not a note on a drawing."""
    hole_id: str = ""
    parent_mark: str = ""
    diameter: float
    # True position in project coordinates.
    center_x: float
    center_y: float
    center_z: float = 0.0
    axis: str = "Z"                  # Direction the drill travels: X, Y or Z
    reference_datum: str = "FRONT_DATUM"
    # How the fabricator actually finds it with a tape measure.
    reference_edge: str = ""         # e.g. "front (truck) end of the tube"
    offset_from_reference: float = 0.0
    plain_instruction: str = ""      # e.g. 'Drill 21/32". Center 3" from the end.'
    note: str = ""
    field_fit: bool = False          # True = do not drill until test-fitted
    status: StatusEnum = StatusEnum.DESIGN

class Weld(BaseModel):
    """
    A declared welded connection between exactly two pieces.

    A weld record is a claim that two pieces meet. The geometry checker decides
    whether that claim is true; it is never taken on trust.
    """
    weld_id: str = ""
    piece_a: str = ""
    piece_b: str = ""
    connected_pieces: List[str] = []   # retained for backwards compatibility
    weld_type: str = "FILLET"          # FILLET, GROOVE, PLUG, TACK
    size: str = "3/16"
    length: Optional[float] = None
    all_around: bool = False
    both_sides: bool = False
    plain_instruction: str = ""        # plain shop English for the fabricator
    joint_note: str = ""
    shop_note: str = ""
    requires_contact: bool = True
    field_fit: bool = False            # do not final-weld until fitted to truck
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
    # Real outside cross-section, used to build the physical envelope.
    section_width: float = 2.0
    section_depth: float = 2.0
    assembly: str = "MAIN_CARRIER" # MAIN_CARRIER, RAMP, STINGER, DETAILS
    cut_type: str = "SQUARE" # SQUARE, ANGLE_CUT, BEVEL, MITER
    cut_angle_left: float = 0.0
    cut_angle_right: float = 0.0
    unit_weight: float # lb/ft
    total_weight: float # lb
    holes: List[Hole] = []
    notes: str = ""
    field_fit: bool = False   # cut/locate on the truck, not from a drawing
    nested_over: str = ""     # this piece slips OVER that piece (sleeve)
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
    # Physical placement. origin is the minimum corner of the part.
    origin: Optional[Point3D] = None
    length_axis: str = "X"    # direction the `length` dimension runs
    width_axis: str = "Y"     # direction the `width` dimension runs
    normal_axis: str = "Z"    # direction the `thickness` runs
    # Formed/brake-bent parts are not flat rectangles; they carry an explicit
    # envelope covering the folded shape.
    bbox_override: Optional[BoxBounds] = None
    position_status: StatusEnum = StatusEnum.DESIGN
    position_note: str = ""
    cut_notes: str = "Shear / Waterjet / Plasma cut"
    status: StatusEnum = StatusEnum.DESIGN

class HingeComponent(BaseModel):
    pin_diameter: float = 0.750
    pin_length: float = 36.00
    sleeve_od: float = 1.250
    sleeve_id: float = 0.875
    sleeve_wall: float = 0.1875
    diametral_clearance: float = 0.125
    sleeve_lengths: List[float] = [4.0] * 7
    pin_material: str = "AISI 1018 Cold Finished Round"
    sleeve_material: str = "ASTM A513 DOM Mechanical Tube"
    retaining_method: str = "Cross-drilled 3/16\" hole 1/2\" from each end - hairpin clip and 3/4\" flat washer"
    status: StatusEnum = StatusEnum.DESIGN

class ContactCheck(BaseModel):
    """Result of testing whether a declared welded joint is real steel-to-steel."""
    weld_id: str = ""
    piece_a: str
    piece_b: str
    overlap_x: float = 0.0
    overlap_y: float = 0.0
    overlap_z: float = 0.0
    gap: float = 0.0
    penetration: float = 0.0
    contact_area: float = 0.0
    min_contact_dim: float = 0.0
    # FACE_CONTACT | KNIFE_EDGE | GAP | INTERFERENCE | MISSING_GEOMETRY
    # FACE_CONTACT | TANGENT_FILLET | KNIFE_EDGE | GAP | INTERFERENCE
    #              | MISSING_GEOMETRY
    result: str = "FACE_CONTACT"
    weld_run: float = 0.0     # how long a bead you can actually run here
    passed: bool = False
    message: str = ""

class InterferenceCheck(BaseModel):
    """Two parts occupying the same space."""
    piece_a: str
    piece_b: str
    overlap_x: float = 0.0
    overlap_y: float = 0.0
    overlap_z: float = 0.0
    penetration: float = 0.0
    volume: float = 0.0
    has_declared_weld: bool = False
    # FIT_REQUIRED | NESTED_FIT | UNINTENDED_CLASH
    category: str = "UNINTENDED_CLASH"
    severity: str = "MAJOR"             # MAJOR | MINOR (trim-to-fit)
    message: str = ""

class EnvelopeResult(BaseModel):
    """Outside size of the finished carrier measured from the actual steel."""
    min_x: float = 0.0
    max_x: float = 0.0
    min_y: float = 0.0
    max_y: float = 0.0
    min_z: float = 0.0
    max_z: float = 0.0
    total_width: float = 0.0
    total_length: float = 0.0
    width_limit: float = 38.0
    within_limit: bool = False
    width_over_limit: float = 0.0
    widest_left_pieces: List[str] = []
    widest_right_pieces: List[str] = []
    # The 38" target applies to the deck / ramp / guide assembly the machine
    # rides on. Under-truck mounting steel is measured separately and is NOT
    # held to that limit - it lives under the truck, not on the road profile.
    usable_width: float = 0.0
    usable_within_limit: bool = False
    usable_over_limit: float = 0.0
    usable_left_pieces: List[str] = []
    usable_right_pieces: List[str] = []
    under_truck_width: float = 0.0
    under_truck_pieces: List[str] = []
    message: str = ""

class HingeCollision(BaseModel):
    moving_piece: str
    fixed_piece: str
    angles_deg: List[float] = []
    max_penetration: float = 0.0
    message: str = ""

class HingeRotationResult(BaseModel):
    pivot_x: float = 0.0
    pivot_z: float = 0.0
    angles_checked: List[float] = []
    rotating_pieces: List[str] = []
    collisions: List[HingeCollision] = []
    clear_angles: List[float] = []
    can_rotate: bool = False
    message: str = ""

class MachineFitResult(BaseModel):
    """
    Does the machine's running gear fit the deck?

    The guides guide the TIRES. The machine's published overall width is a body
    dimension measured well above the 3" guides and is not what has to pass
    between them. Whether any bodywork brushes a guide is settled by rolling the
    machine on during fit-up, which is normal practice, not an open question.
    """
    rear_tire_width: float = 0.0
    track_flat_width: float = 0.0
    tire_side_clearance: float = 0.0     # slack per side on one track
    guide_clear_width: Optional[float] = None
    tracks_fit_tires: Optional[bool] = None
    deck_usable_length: float = 0.0
    machine_length_field: float = 0.0
    front_overhang: float = 0.0
    status: str = "PASS"                 # PASS | FAIL
    notes: List[str] = []
    fit_up_checks: List[str] = []        # things confirmed by rolling it on

class GeometryCheckReport(BaseModel):
    contacts: List[ContactCheck] = []
    interferences: List[InterferenceCheck] = []
    envelope: EnvelopeResult = EnvelopeResult()
    hinge: HingeRotationResult = HingeRotationResult()
    machine: MachineFitResult = MachineFitResult()
    unpositioned_parts: List[str] = []
    member_count: int = 0
    plate_count: int = 0
    positioned_member_count: int = 0
    positioned_plate_count: int = 0
    weld_count: int = 0
    failed_contact_count: int = 0
    unintended_clash_count: int = 0
    major_clash_count: int = 0
    overall_status: str = "FAIL"
    summary: List[str] = []

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
    yields_at_g: float = 0.0
    target_safety_factor: float = 2.00
    controlling_load_case: str = "VERTICAL"
    controlling_stress_psi: float = 0.0
    is_adequate: bool = False
    status: str = "FAIL"
    load_cases: Dict[str, Any] = {}
    hinge_check: Optional[Dict[str, Any]] = None
    reinforcement_recommendations: List[str] = []
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
    field_fit: bool = False
    notes: str = ""

class CutListRow(BaseModel):
    piece_mark: str
    section: str
    grade: str = "ASTM A500 Gr B"
    cut_length: float
    quantity: int
    cut_type: str = "SQUARE"
    cut_angle_left: float = 0.0
    cut_angle_right: float = 0.0
    field_fit: bool = False
    notes: str = ""

class PurchaseRow(BaseModel):
    category: str = "LINEAR_STOCK" # LINEAR_STOCK, PLATE, GRATING, HARDWARE
    section: str
    grade: str
    stick_length: float = 0.0
    quantity: int = 1
    total_purchased_length: float = 0.0
    total_purchased_weight: float = 0.0
    unit_size: str = ""
    notes: str = ""

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
