import math
from typing import List, Dict, Any, Tuple
from models import (
    ProjectParameters, StatusEnum, ParameterItem, Point3D, Hole, Weld,
    Member, Plate, HingeComponent, StructuralCheckResult, BomRow, CutListRow
)

# Central Material & Shape Library
# Stores exact dimensional, physical, and structural section properties
MATERIAL_LIBRARY = {
    # Structural Tubing (ASTM A500 Gr B, Fy = 46 ksi)
    "2x2x3/16 Tube": {
        "type": "HSS",
        "name": "HSS 2x2x3/16",
        "width": 2.00,
        "height": 2.00,
        "thickness": 0.1875,
        "grade": "ASTM A500 Gr B",
        "wt_per_ft": 4.32,
        "area": 1.07,
        "section_modulus": 0.584,
        "category": "TUBE"
    },
    "2x2x1/4 Tube": {
        "type": "HSS",
        "name": "HSS 2x2x1/4",
        "width": 2.00,
        "height": 2.00,
        "thickness": 0.250,
        "grade": "ASTM A500 Gr B",
        "wt_per_ft": 5.41,
        "area": 1.36,
        "section_modulus": 0.697,
        "category": "TUBE"
    },
    # Structural Angle (ASTM A36, Fy = 36 ksi)
    "2x2x3/16 Angle": {
        "type": "ANGLE",
        "name": "L 2x2x3/16",
        "width": 2.00,
        "height": 2.00,
        "thickness": 0.1875,
        "grade": "ASTM A36",
        "wt_per_ft": 2.44,
        "area": 0.715,
        "section_modulus": 0.247,
        "category": "ANGLE"
    },
    "2x2x1/4 Angle": {
        "type": "ANGLE",
        "name": "L 2x2x1/4",
        "width": 2.00,
        "height": 2.00,
        "thickness": 0.250,
        "grade": "ASTM A36",
        "wt_per_ft": 3.19,
        "area": 0.938,
        "section_modulus": 0.317,
        "category": "ANGLE"
    },
    # Solid Round Pin Stock (AISI 1018 Cold Finished)
    "3/4 Round Bar": {
        "type": "ROUND",
        "name": "3/4\" Round Bar",
        "diameter": 0.75,
        "thickness": 0.75,
        "grade": "AISI 1018 CF",
        "wt_per_ft": 1.502,
        "area": 0.442,
        "category": "BAR"
    },
    # Mechanical Sleeve Tubing (ASTM A513 DOM)
    "1.125x0.188 DOM Tube": {
        "type": "ROUND_TUBE",
        "name": "1-1/8\" OD x 3/16\" Wall DOM Sleeve",
        "od": 1.125,
        "id": 0.750,
        "grade": "ASTM A513 DOM",
        "wt_per_ft": 1.88,
        "category": "TUBE"
    },
    # Steel Plate (ASTM A36)
    "1/4 Plate": {
        "type": "PLATE",
        "name": "1/4\" Steel Plate",
        "thickness": 0.250,
        "grade": "ASTM A36",
        "density_lb_in3": 0.2836,
        "category": "PLATE"
    },
    "3/16 Plate": {
        "type": "PLATE",
        "name": "3/16\" Steel Plate",
        "thickness": 0.1875,
        "grade": "ASTM A36",
        "density_lb_in3": 0.2836,
        "category": "PLATE"
    },
    "3/8 Plate": {
        "type": "PLATE",
        "name": "3/8\" Steel Plate",
        "thickness": 0.375,
        "grade": "ASTM A36",
        "density_lb_in3": 0.2836,
        "category": "PLATE"
    },
    # Traction Surface
    "Expanded Metal #9 1-1/2": {
        "type": "GRATING",
        "name": "#9 1-1/2\" Flattened Expanded Metal",
        "thickness": 0.134,
        "grade": "ASTM A36 Carbon Steel",
        "wt_per_sqft": 1.80,
        "category": "GRATING"
    }
}

def get_project_provenance(params: ProjectParameters) -> Dict[str, ParameterItem]:
    """Returns complete provenance metadata for all project design values."""
    return {
        "carrier_width": ParameterItem(
            name="carrier_width",
            value=params.carrier_width,
            units="in",
            status=StatusEnum.MEASURED,
            description="Carrier overall outside frame width",
            source_note="Field-proven existing carrier dimension; fits truck receiver spacing and Z-Spray width.",
            required_before_fabrication=False
        ),
        "carrier_deck_length": ParameterItem(
            name="carrier_deck_length",
            value=params.carrier_deck_length,
            units="in",
            status=StatusEnum.MEASURED,
            description="Carrier deck length from front stop to ramp hinge centerline",
            source_note="Field-proven dimension on existing carrier; provides safe wheel base envelope.",
            required_before_fabrication=False
        ),
        "deck_height": ParameterItem(
            name="deck_height",
            value=params.deck_height,
            units="in",
            status=StatusEnum.DESIGN,
            description="Target running surface deck height above ground",
            source_note="Original carrier target was 17.0\"; old carrier sagged to 16.0\". Target 17.0\" without sag.",
            required_before_fabrication=False
        ),
        "ramp_length": ParameterItem(
            name="ramp_length",
            value=params.ramp_length,
            units="in",
            status=StatusEnum.MEASURED,
            description="Rigid ramp overall length from hinge centerline to tip",
            source_note="Single rigid hinged assembly; measured on existing carrier with welded extension.",
            required_before_fabrication=False
        ),
        "ramp_clearance": ParameterItem(
            name="ramp_clearance",
            value=params.ramp_clearance,
            units="in",
            status=StatusEnum.DESIGN,
            description="Nominal clearance between machine rear tires and upright ramp",
            source_note="Target 1.0\" clearance when machine is pulled tight forward against front stop.",
            required_before_fabrication=False
        ),
        "receiver_spacing": ParameterItem(
            name="receiver_spacing",
            value=params.receiver_spacing,
            units="in",
            status=StatusEnum.MEASURED,
            description="Truck twin receiver centerline-to-centerline spacing",
            source_note="Calculated from 40.0\" outside-to-outside span minus 2.0\" tube width = 38.00\" exact.",
            required_before_fabrication=False
        ),
        "receiver_outside_span": ParameterItem(
            name="receiver_outside_span",
            value=params.receiver_outside_span,
            units="in",
            status=StatusEnum.MEASURED,
            description="Truck receiver tubes outside-to-outside span",
            source_note="Field measurement on 2015 Ford F-350 flatbed rear mount tubes.",
            required_before_fabrication=False
        ),
        "receiver_tube_width": ParameterItem(
            name="receiver_tube_width",
            value=params.receiver_tube_width,
            units="in",
            status=StatusEnum.MEASURED,
            description="Outside width of truck receiver tubes",
            source_note="Standard 2.00\" OD hitch receiver tubes.",
            required_before_fabrication=False
        ),
        "stinger_insertion_length": ParameterItem(
            name="stinger_insertion_length",
            value=params.stinger_insertion_length,
            units="in",
            status=StatusEnum.ESTIMATED_UNVERIFIED,
            description="Stinger penetration depth forward into truck receiver tube",
            source_note="FIELD VERIFICATION MANDATORY: Measure depth from receiver mouth to internal obstruction on F-350.",
            required_before_fabrication=True
        ),
        "hitch_pin_hole_setback": ParameterItem(
            name="hitch_pin_hole_setback",
            value=params.hitch_pin_hole_setback,
            units="in",
            status=StatusEnum.ESTIMATED_UNVERIFIED,
            description="Hitch pin hole centerline setback from stinger front tip",
            source_note="FIELD VERIFICATION MANDATORY: Measure hole centerline on truck receiver before drilling stingers.",
            required_before_fabrication=True
        ),
        "truck_suspension_drop": ParameterItem(
            name="truck_suspension_drop",
            value=params.truck_suspension_drop,
            units="in",
            status=StatusEnum.ESTIMATED_UNVERIFIED,
            description="Anticipated rear suspension squat under 1,400 lb cantilevered carrier load",
            source_note="FIELD VERIFICATION MANDATORY: Measure F-350 bumper height unloaded vs 1,000 lb loaded on flatbed.",
            required_before_fabrication=True
        ),
        "machine_curb_weight": ParameterItem(
            name="machine_curb_weight",
            value=params.machine_curb_weight,
            units="lb",
            status=StatusEnum.OEM,
            description="2026 Z-Spray Junior (Model ZSX3624) dry curb weight",
            source_note="OEM published specification.",
            required_before_fabrication=False
        ),
        "fertilizer_payload": ParameterItem(
            name="fertilizer_payload",
            value=params.fertilizer_hopper_weight + params.fertilizer_trays_weight,
            units="lb",
            status=StatusEnum.OEM,
            description="Maximum dry fertilizer carrying capacity (150 lb hopper + 2x50 lb trays)",
            source_note="OEM published rated hopper and tray capacities.",
            required_before_fabrication=False
        ),
        "spray_liquid_weight": ParameterItem(
            name="spray_liquid_weight",
            value=round(params.spray_tank_gallons * params.liquid_density_lb_gal, 1),
            units="lb",
            status=StatusEnum.CALCULATED,
            description="Full spray tank liquid weight (24 gallons @ 8.34 lb/gal)",
            source_note="Calculated from OEM tank volume and water density.",
            required_before_fabrication=False
        )
    }

def calculate_structural_checks(params: ProjectParameters, carrier_dead_weight: float) -> StructuralCheckResult:
    """Calculates engineering load rollup, cantilever moment, and stinger stress."""
    # Machine working payload
    chem_wt = params.spray_tank_gallons * params.liquid_density_lb_gal
    fert_wt = params.fertilizer_hopper_weight + params.fertilizer_trays_weight
    payload_wt = params.machine_curb_weight + chem_wt + fert_wt
    
    total_suspended = payload_wt + carrier_dead_weight
    
    # Dynamic vertical force (e.g. 2.0g bump)
    dynamic_vert = total_suspended * params.vertical_dynamic_factor
    
    # Center of gravity of suspended mass located approximately at 50% of deck length
    # Z-Spray CG is biased slightly rearward of center of wheelbase (~32" from front stop)
    cg_distance_from_hitch = params.carrier_deck_length * 0.50
    
    # Cantilever bending moment at mouth of truck receivers
    dynamic_moment = dynamic_vert * cg_distance_from_hitch
    
    # Symmetric twin receiver share
    stinger_reaction = dynamic_vert / 2.0
    stinger_moment = dynamic_moment / 2.0
    
    # Section modulus of stinger tube
    stinger_mat = MATERIAL_LIBRARY.get(params.stinger_section, MATERIAL_LIBRARY["2x2x1/4 Tube"])
    S = stinger_mat.get("section_modulus", 0.697)
    
    # Bending stress: sigma = M / S
    stinger_stress = stinger_moment / S if S > 0 else 0.0
    
    yield_strength = params.material_yield_strength
    # Factor of safety based on yield strength under dynamic shock
    fos = yield_strength / stinger_stress if stinger_stress > 0 else 0.0
    
    adequate = fos >= 1.0 # Dynamic shock load has FOS >= 1.0; static FOS will be >= 2.0
    
    notes = [
        f"Total payload rollup: {payload_wt:.1f} lb (Machine: {params.machine_curb_weight} lb, Fert: {fert_wt} lb, Liquid: {chem_wt:.1f} lb).",
        f"Carrier self-weight: {carrier_dead_weight:.1f} lb; Total suspended deadweight: {total_suspended:.1f} lb.",
        f"Design dynamic factor: {params.vertical_dynamic_factor}g vertical shock load = {dynamic_vert:.1f} lb peak load.",
        f"Cantilever moment at truck receiver interface: {dynamic_moment:.0f} in-lb ({stinger_moment:.0f} in-lb per stinger).",
        f"Stinger bending stress under 2.0g shock: {stinger_stress:.0f} psi vs {yield_strength:.0f} psi yield (Dynamic FOS: {fos:.2f}).",
        f"Static (1.0g highway cruising) Factor of Safety: {fos * 2.0:.2f}."
    ]
    
    return StructuralCheckResult(
        payload_weight=round(payload_wt, 1),
        carrier_dead_weight=round(carrier_dead_weight, 1),
        total_suspended_weight=round(total_suspended, 1),
        dynamic_vertical_load=round(dynamic_vert, 1),
        dynamic_moment_in_lb=round(dynamic_moment, 0),
        stinger_reaction_force_lb=round(stinger_reaction, 1),
        stinger_bending_stress_psi=round(stinger_stress, 0),
        yield_strength_psi=yield_strength,
        factor_of_safety=round(fos, 2),
        is_adequate=adequate,
        notes=notes
    )

def generate_fabrication_assembly(params: ProjectParameters) -> Dict[str, Any]:
    """
    Constructs the true 3D Parametric Fabrication Assembly.
    Establishes coordinate system:
      X = 0 at front datum (truck face)
      Y = 0 at carrier centerline (transverse +/-19")
      Z = 0 at deck running surface
    """
    members: List[Member] = []
    plates: List[Plate] = []
    welds: List[Weld] = []
    
    # -------------------------------------------------------------
    # 1. MAIN CARRIER WELDMENT
    # -------------------------------------------------------------
    # Longitudinal Frame Outer Rails (M1-L, M1-R)
    # Outside edge is at Y = +/- 19.00". 2x2 Tube center is at Y = +/- 18.00"
    m1_len = params.carrier_deck_length
    m1_mat = MATERIAL_LIBRARY["2x2x3/16 Tube"]
    m1_wt = (m1_len / 12.0) * m1_mat["wt_per_ft"]
    
    members.append(Member(
        piece_mark="M1-L",
        description="Main Outer Frame Tube - Left (Driver Side)",
        section="2x2x3/16 Tube",
        grade=m1_mat["grade"],
        length=m1_len,
        quantity=1,
        start_pt=Point3D(x=0.0, y=-18.0, z=-1.0),
        end_pt=Point3D(x=m1_len, y=-18.0, z=-1.0),
        orientation="X",
        assembly="MAIN_CARRIER",
        cut_type="SQUARE",
        unit_weight=m1_mat["wt_per_ft"],
        total_weight=round(m1_wt, 2),
        notes="Full length deck longitudinal tube. Outer edge defines 38\" overall width datum.",
        status=StatusEnum.DESIGN
    ))
    members.append(Member(
        piece_mark="M1-R",
        description="Main Outer Frame Tube - Right (Passenger Side)",
        section="2x2x3/16 Tube",
        grade=m1_mat["grade"],
        length=m1_len,
        quantity=1,
        start_pt=Point3D(x=0.0, y=18.0, z=-1.0),
        end_pt=Point3D(x=m1_len, y=18.0, z=-1.0),
        orientation="X",
        assembly="MAIN_CARRIER",
        cut_type="SQUARE",
        unit_weight=m1_mat["wt_per_ft"],
        total_weight=round(m1_wt, 2),
        notes="Full length deck longitudinal tube. Outer edge defines 38\" overall width datum.",
        status=StatusEnum.DESIGN
    ))
    
    # Longitudinal Inner Track Support Rails (M2-L, M2-R)
    # Positioned at Y = +/- 7.00" (inside edge of 12" wide track, leaving 14" center open gap)
    m2_mat = MATERIAL_LIBRARY["2x2x3/16 Angle"]
    m2_wt = (m1_len / 12.0) * m2_mat["wt_per_ft"]
    members.append(Member(
        piece_mark="M2-L",
        description="Inner Track Support Angle - Left",
        section="2x2x3/16 Angle",
        grade=m2_mat["grade"],
        length=m1_len,
        quantity=1,
        start_pt=Point3D(x=0.0, y=-7.0, z=-1.0),
        end_pt=Point3D(x=m1_len, y=-7.0, z=-1.0),
        orientation="X",
        assembly="MAIN_CARRIER",
        cut_type="SQUARE",
        unit_weight=m2_mat["wt_per_ft"],
        total_weight=round(m2_wt, 2),
        notes="Leg down, toe out. Supports inside edge of 12\" wheel track.",
        status=StatusEnum.DESIGN
    ))
    members.append(Member(
        piece_mark="M2-R",
        description="Inner Track Support Angle - Right",
        section="2x2x3/16 Angle",
        grade=m2_mat["grade"],
        length=m1_len,
        quantity=1,
        start_pt=Point3D(x=0.0, y=7.0, z=-1.0),
        end_pt=Point3D(x=m1_len, y=7.0, z=-1.0),
        orientation="X",
        assembly="MAIN_CARRIER",
        cut_type="SQUARE",
        unit_weight=m2_mat["wt_per_ft"],
        total_weight=round(m2_wt, 2),
        notes="Leg down, toe out. Supports inside edge of 12\" wheel track.",
        status=StatusEnum.DESIGN
    ))
    
    # Crossmembers (C1, C2, C3, C4)
    # Span between inside faces of M1 rails: 38.0 - 2 * 2.0 = 34.00"
    cm_len = params.carrier_width - 4.00
    c_mat = MATERIAL_LIBRARY["2x2x3/16 Tube"]
    c_wt = (cm_len / 12.0) * c_mat["wt_per_ft"]
    
    crossmember_locs = [
        ("C1", 1.00, "Front Header Crossmember (Front Datum X=0)"),
        ("C2", 18.00, "Forward Intermediate Crossmember (Ties Stinger Overlap)"),
        ("C3", 38.00, "Mid-Deck Crossmember (Under Machine Rear Axle Position)"),
        ("C4", 62.00, "Rear Hinge Crossmember (Mounts Ramp Hinge Sleeves)")
    ]
    for mark, x_loc, desc in crossmember_locs:
        members.append(Member(
            piece_mark=mark,
            description=desc,
            section="2x2x3/16 Tube",
            grade=c_mat["grade"],
            length=cm_len,
            quantity=1,
            start_pt=Point3D(x=x_loc, y=-17.0, z=-1.0),
            end_pt=Point3D(x=x_loc, y=17.0, z=-1.0),
            orientation="Y",
            assembly="MAIN_CARRIER",
            cut_type="SQUARE",
            unit_weight=c_mat["wt_per_ft"],
            total_weight=round(c_wt, 2),
            notes=f"Located at X = {x_loc:.2f}\" from front datum.",
            status=StatusEnum.DESIGN
        ))
        welds.append(Weld(
            connected_pieces=[mark, "M1-L", "M1-R"],
            weld_type="FILLET",
            size="3/16",
            all_around=True,
            shop_note=f"3/16\" Fillet weld all around joint at X={x_loc:.2f}\"",
            status=StatusEnum.DESIGN
        ))
        
    # Flared Outer Wheel Guides on Carrier Deck (FG1-L, FG1-R)
    # Formed 3/16 plate or angle along outer edges to guide tires
    fg_mat = MATERIAL_LIBRARY["3/16 Plate"]
    fg_len = m1_len
    # 3\" vertical + 1.5\" flare = ~4.5\" developed width
    fg_plate_wt = (fg_len * 4.5 * 0.1875) * fg_mat["density_lb_in3"]
    plates.append(Plate(
        piece_mark="FG1-L",
        description="Flared Wheel Guide - Carrier Left",
        thickness=0.1875,
        width=4.50,
        length=fg_len,
        grade=fg_mat["grade"],
        material="3/16\" Steel Plate",
        quantity=1,
        unit_weight=round(fg_plate_wt, 2),
        total_weight=round(fg_plate_wt, 2),
        assembly="MAIN_CARRIER",
        cut_notes="Brake form 45-deg flare: 3\" vertical leg, 1.5\" outward flare.",
        status=StatusEnum.DESIGN
    ))
    plates.append(Plate(
        piece_mark="FG1-R",
        description="Flared Wheel Guide - Carrier Right",
        thickness=0.1875,
        width=4.50,
        length=fg_len,
        grade=fg_mat["grade"],
        material="3/16\" Steel Plate",
        quantity=1,
        unit_weight=round(fg_plate_wt, 2),
        total_weight=round(fg_plate_wt, 2),
        assembly="MAIN_CARRIER",
        cut_notes="Brake form 45-deg flare: 3\" vertical leg, 1.5\" outward flare.",
        status=StatusEnum.DESIGN
    ))
    
    # Traction Grating for Deck (EM1-L, EM1-R)
    # Spans 12\" width by 63\" length
    em_mat = MATERIAL_LIBRARY["Expanded Metal #9 1-1/2"]
    em_sqft = (12.0 * m1_len) / 144.0
    em_wt = em_sqft * em_mat["wt_per_sqft"]
    plates.append(Plate(
        piece_mark="EM1-L",
        description="Traction Grating - Deck Left Track",
        thickness=0.134,
        width=12.00,
        length=m1_len,
        grade=em_mat["grade"],
        material="#9 1-1/2\" Expanded Metal",
        quantity=1,
        unit_weight=round(em_wt, 2),
        total_weight=round(em_wt, 2),
        assembly="MAIN_CARRIER",
        cut_notes="Shear cut 12\" x 63\". Tack weld to M1-L and M2-L @ 6\" O.C.",
        status=StatusEnum.DESIGN
    ))
    plates.append(Plate(
        piece_mark="EM1-R",
        description="Traction Grating - Deck Right Track",
        thickness=0.134,
        width=12.00,
        length=m1_len,
        grade=em_mat["grade"],
        material="#9 1-1/2\" Expanded Metal",
        quantity=1,
        unit_weight=round(em_wt, 2),
        total_weight=round(em_wt, 2),
        assembly="MAIN_CARRIER",
        cut_notes="Shear cut 12\" x 63\". Tack weld to M1-R and M2-R @ 6\" O.C.",
        status=StatusEnum.DESIGN
    ))

    # -------------------------------------------------------------
    # 2. TWIN RECEIVER / STINGER ASSEMBLY
    # -------------------------------------------------------------
    # Truck receiver tubes center spacing = 38.00" (Y = +/- 19.00")
    # Outside span = 40.00", inside span = 36.00".
    # Stingers S1-L and S1-R fit directly under outer longitudinal members M1-L and M1-R.
    # Total stinger length = insertion (18.00" UNVERIFIED) + underframe overlap (18.00" to C2) = 36.00"
    stinger_mat = MATERIAL_LIBRARY[params.stinger_section]
    stinger_total_len = params.stinger_insertion_length + params.stinger_overlap_length
    stinger_wt = (stinger_total_len / 12.0) * stinger_mat["wt_per_ft"]
    
    members.append(Member(
        piece_mark="S1-L",
        description="Mount Stinger - Left (Driver Side)",
        section=params.stinger_section,
        grade=stinger_mat["grade"],
        length=stinger_total_len,
        quantity=1,
        start_pt=Point3D(x=-params.stinger_insertion_length, y=-19.0, z=-3.0),
        end_pt=Point3D(x=params.stinger_overlap_length, y=-19.0, z=-3.0),
        orientation="X",
        assembly="STINGER",
        cut_type="SQUARE",
        unit_weight=stinger_mat["wt_per_ft"],
        total_weight=round(stinger_wt, 2),
        notes="Insertion length & pin hole UNVERIFIED. Verify truck receiver depth before cutting.",
        status=StatusEnum.ESTIMATED_UNVERIFIED
    ))
    members.append(Member(
        piece_mark="S1-R",
        description="Mount Stinger - Right (Passenger Side)",
        section=params.stinger_section,
        grade=stinger_mat["grade"],
        length=stinger_total_len,
        quantity=1,
        start_pt=Point3D(x=-params.stinger_insertion_length, y=19.0, z=-3.0),
        end_pt=Point3D(x=params.stinger_overlap_length, y=19.0, z=-3.0),
        orientation="X",
        assembly="STINGER",
        cut_type="SQUARE",
        unit_weight=stinger_mat["wt_per_ft"],
        total_weight=round(stinger_wt, 2),
        notes="Insertion length & pin hole UNVERIFIED. Verify truck receiver depth before cutting.",
        status=StatusEnum.ESTIMATED_UNVERIFIED
    ))
    
    # Stinger Underframe Reinforcement Gussets (G1)
    g1_mat = MATERIAL_LIBRARY["1/4 Plate"]
    g1_wt = (4.0 * 8.0 * 0.5 * 0.250) * g1_mat["density_lb_in3"]
    for i, side in enumerate(["L", "R"]):
        plates.append(Plate(
            piece_mark=f"G1-{side}1",
            description=f"Stinger Gusset Front - {side}",
            thickness=0.250,
            width=4.00,
            length=8.00,
            profile_pts=[(0, 0), (8, 0), (0, 4)],
            grade=g1_mat["grade"],
            material="1/4\" Steel Plate",
            quantity=1,
            unit_weight=round(g1_wt, 2),
            total_weight=round(g1_wt, 2),
            assembly="STINGER",
            cut_notes="Triangular gusset 4\" x 8\". Welded along C1 header to stinger.",
            status=StatusEnum.DESIGN
        ))
        plates.append(Plate(
            piece_mark=f"G1-{side}2",
            description=f"Stinger Gusset Rear - {side}",
            thickness=0.250,
            width=4.00,
            length=8.00,
            profile_pts=[(0, 0), (8, 0), (0, 4)],
            grade=g1_mat["grade"],
            material="1/4\" Steel Plate",
            quantity=1,
            unit_weight=round(g1_wt, 2),
            total_weight=round(g1_wt, 2),
            assembly="STINGER",
            cut_notes="Triangular gusset 4\" x 8\". Welded along C2 crossmember to stinger.",
            status=StatusEnum.DESIGN
        ))

    # -------------------------------------------------------------
    # 3. RAMP WELDMENT (ONE Rigid 61.00" assembly)
    # -------------------------------------------------------------
    r_len = params.ramp_length
    r1_mat = MATERIAL_LIBRARY["2x2x3/16 Tube"]
    r1_wt = (r_len / 12.0) * r1_mat["wt_per_ft"]
    
    # Ramp Outer Side Tubes (R1-L, R1-R)
    members.append(Member(
        piece_mark="R1-L",
        description="Ramp Outer Side Tube - Left",
        section="2x2x3/16 Tube",
        grade=r1_mat["grade"],
        length=r_len,
        quantity=1,
        start_pt=Point3D(x=params.carrier_deck_length, y=-18.0, z=-1.0),
        end_pt=Point3D(x=params.carrier_deck_length + r_len, y=-18.0, z=-1.0),
        orientation="X",
        assembly="RAMP",
        cut_type="MITER_45",
        cut_angle_right=16.2, # Deployed ground contact beveled foot
        unit_weight=r1_mat["wt_per_ft"],
        total_weight=round(r1_wt, 2),
        notes="Main rigid ramp side member. Pivots at carrier hinge.",
        status=StatusEnum.MEASURED
    ))
    members.append(Member(
        piece_mark="R1-R",
        description="Ramp Outer Side Tube - Right",
        section="2x2x3/16 Tube",
        grade=r1_mat["grade"],
        length=r_len,
        quantity=1,
        start_pt=Point3D(x=params.carrier_deck_length, y=18.0, z=-1.0),
        end_pt=Point3D(x=params.carrier_deck_length + r_len, y=18.0, z=-1.0),
        orientation="X",
        assembly="RAMP",
        cut_type="MITER_45",
        cut_angle_right=16.2,
        unit_weight=r1_mat["wt_per_ft"],
        total_weight=round(r1_wt, 2),
        notes="Main rigid ramp side member. Pivots at carrier hinge.",
        status=StatusEnum.MEASURED
    ))
    
    # Ramp Inner Support Rails (R2-L, R2-R)
    r2_mat = MATERIAL_LIBRARY["2x2x3/16 Angle"]
    r2_wt = (r_len / 12.0) * r2_mat["wt_per_ft"]
    members.append(Member(
        piece_mark="R2-L",
        description="Ramp Inner Track Support - Left",
        section="2x2x3/16 Angle",
        grade=r2_mat["grade"],
        length=r_len,
        quantity=1,
        start_pt=Point3D(x=params.carrier_deck_length, y=-7.0, z=-1.0),
        end_pt=Point3D(x=params.carrier_deck_length + r_len, y=-7.0, z=-1.0),
        orientation="X",
        assembly="RAMP",
        cut_type="SQUARE",
        unit_weight=r2_mat["wt_per_ft"],
        total_weight=round(r2_wt, 2),
        notes="Leg down, toe out. Aligns with carrier M2-L track.",
        status=StatusEnum.DESIGN
    ))
    members.append(Member(
        piece_mark="R2-R",
        description="Ramp Inner Track Support - Right",
        section="2x2x3/16 Angle",
        grade=r2_mat["grade"],
        length=r_len,
        quantity=1,
        start_pt=Point3D(x=params.carrier_deck_length, y=7.0, z=-1.0),
        end_pt=Point3D(x=params.carrier_deck_length + r_len, y=7.0, z=-1.0),
        orientation="X",
        assembly="RAMP",
        cut_type="SQUARE",
        unit_weight=r2_mat["wt_per_ft"],
        total_weight=round(r2_wt, 2),
        notes="Leg down, toe out. Aligns with carrier M2-R track.",
        status=StatusEnum.DESIGN
    ))
    
    # Ramp Crossmembers (RC1 to RC5)
    # Spaced at 0", 15", 30", 45", 60" along the 61" ramp
    rc_mat = MATERIAL_LIBRARY["2x2x3/16 Angle"]
    rc_len = cm_len
    rc_wt = (rc_len / 12.0) * rc_mat["wt_per_ft"]
    ramp_cm_locs = [
        ("RC1", 0.50, "Ramp Head Crossmember (Hinge Anchor)"),
        ("RC2", 15.00, "Ramp Intermediate Crossmember #1"),
        ("RC3", 30.00, "Ramp Intermediate Crossmember #2"),
        ("RC4", 45.00, "Ramp Intermediate Crossmember #3"),
        ("RC5", 60.00, "Ramp Foot Crossmember (Ground Contact Tie)")
    ]
    for mark, dist, desc in ramp_cm_locs:
        members.append(Member(
            piece_mark=mark,
            description=desc,
            section="2x2x3/16 Angle",
            grade=rc_mat["grade"],
            length=rc_len,
            quantity=1,
            start_pt=Point3D(x=params.carrier_deck_length + dist, y=-17.0, z=-1.0),
            end_pt=Point3D(x=params.carrier_deck_length + dist, y=17.0, z=-1.0),
            orientation="Y",
            assembly="RAMP",
            cut_type="SQUARE",
            unit_weight=rc_mat["wt_per_ft"],
            total_weight=round(rc_wt, 2),
            notes=f"Located at {dist:.1f}\" along ramp from hinge line.",
            status=StatusEnum.DESIGN
        ))
        
    # Ramp Flared Outer Guides (RFG1-L, RFG1-R)
    rfg_mat = MATERIAL_LIBRARY["3/16 Plate"]
    rfg_plate_wt = (r_len * 4.5 * 0.1875) * rfg_mat["density_lb_in3"]
    plates.append(Plate(
        piece_mark="RFG1-L",
        description="Ramp Flared Wheel Guide - Left",
        thickness=0.1875,
        width=4.50,
        length=r_len,
        grade=rfg_mat["grade"],
        material="3/16\" Steel Plate",
        quantity=1,
        unit_weight=round(rfg_plate_wt, 2),
        total_weight=round(rfg_plate_wt, 2),
        assembly="RAMP",
        cut_notes="Brake form 45-deg flare: 3\" vertical leg, 1.5\" outward flare.",
        status=StatusEnum.DESIGN
    ))
    plates.append(Plate(
        piece_mark="RFG1-R",
        description="Ramp Flared Wheel Guide - Right",
        thickness=0.1875,
        width=4.50,
        length=r_len,
        grade=rfg_mat["grade"],
        material="3/16\" Steel Plate",
        quantity=1,
        unit_weight=round(rfg_plate_wt, 2),
        total_weight=round(rfg_plate_wt, 2),
        assembly="RAMP",
        cut_notes="Brake form 45-deg flare: 3\" vertical leg, 1.5\" outward flare.",
        status=StatusEnum.DESIGN
    ))
    
    # Ramp Traction Grating (REM1-L, REM1-R)
    rem_sqft = (12.0 * r_len) / 144.0
    rem_wt = rem_sqft * em_mat["wt_per_sqft"]
    plates.append(Plate(
        piece_mark="REM1-L",
        description="Traction Grating - Ramp Left Track",
        thickness=0.134,
        width=12.00,
        length=r_len,
        grade=em_mat["grade"],
        material="#9 1-1/2\" Expanded Metal",
        quantity=1,
        unit_weight=round(rem_wt, 2),
        total_weight=round(rem_wt, 2),
        assembly="RAMP",
        cut_notes="Shear cut 12\" x 61\". Tack weld to R1-L and R2-L @ 6\" O.C.",
        status=StatusEnum.DESIGN
    ))
    plates.append(Plate(
        piece_mark="REM1-R",
        description="Traction Grating - Ramp Right Track",
        thickness=0.134,
        width=12.00,
        length=r_len,
        grade=em_mat["grade"],
        material="#9 1-1/2\" Expanded Metal",
        quantity=1,
        unit_weight=round(rem_wt, 2),
        total_weight=round(rem_wt, 2),
        assembly="RAMP",
        cut_notes="Shear cut 12\" x 61\". Tack weld to R1-R and R2-R @ 6\" O.C.",
        status=StatusEnum.DESIGN
    ))
    
    # Ramp Ground Transition Foot Plate (RF1)
    rf_mat = MATERIAL_LIBRARY["1/4 Plate"]
    rf_wt = (3.0 * params.carrier_width * 0.250) * rf_mat["density_lb_in3"]
    plates.append(Plate(
        piece_mark="RF1",
        description="Ramp Ground Transition Foot Plate",
        thickness=0.250,
        width=3.00,
        length=params.carrier_width,
        grade=rf_mat["grade"],
        material="1/4\" Steel Plate",
        quantity=1,
        unit_weight=round(rf_wt, 2),
        total_weight=round(rf_wt, 2),
        assembly="RAMP",
        cut_notes="Beveled edge 15 degrees for smooth tire transition from grade.",
        status=StatusEnum.DESIGN
    ))

    # -------------------------------------------------------------
    # 4. HINGE ASSEMBLY DETAILS
    # -------------------------------------------------------------
    # Hinge Pin: 3/4" Cold Rolled Round Bar, 40.00" length
    pin_mat = MATERIAL_LIBRARY["3/4 Round Bar"]
    pin_wt = (40.0 / 12.0) * pin_mat["wt_per_ft"]
    members.append(Member(
        piece_mark="P1",
        description="Ramp Hinge Main Pin",
        section="3/4 Round Bar",
        grade=pin_mat["grade"],
        length=40.00,
        quantity=1,
        start_pt=Point3D(x=params.carrier_deck_length, y=-20.0, z=-1.0),
        end_pt=Point3D(x=params.carrier_deck_length, y=20.0, z=-1.0),
        orientation="Y",
        assembly="HINGE",
        cut_type="SQUARE",
        unit_weight=pin_mat["wt_per_ft"],
        total_weight=round(pin_wt, 2),
        notes="Drill 3/16\" cotter/linch pin hole 0.50\" from each end.",
        status=StatusEnum.DESIGN
    ))
    
    # Hinge Sleeves: DOM Tubing barrels (HS1 to HS4), 3.50" long each
    sleeve_mat = MATERIAL_LIBRARY["1.125x0.188 DOM Tube"]
    sleeve_wt = (3.50 / 12.0) * sleeve_mat["wt_per_ft"]
    for i in range(1, 5):
        owner = "Carrier" if i in [1, 4] else "Ramp"
        members.append(Member(
            piece_mark=f"HS{i}",
            description=f"Hinge Sleeve Barrel - {owner} ({i}/4)",
            section="1.125x0.188 DOM Tube",
            grade=sleeve_mat["grade"],
            length=3.50,
            quantity=1,
            start_pt=Point3D(x=params.carrier_deck_length, y=-15.0 + (i * 6.0), z=-1.0),
            end_pt=Point3D(x=params.carrier_deck_length, y=-11.5 + (i * 6.0), z=-1.0),
            orientation="Y",
            assembly="HINGE",
            cut_type="SQUARE",
            unit_weight=sleeve_mat["wt_per_ft"],
            total_weight=round(sleeve_wt, 2),
            notes=f"1-1/8\" OD x 3/4\" ID DOM mechanical sleeve. Welded to {owner} rear structure.",
            status=StatusEnum.DESIGN
        ))
    
    # -------------------------------------------------------------
    # 5. INDIVIDUAL FABRICATED DETAILS / BRACKETS / GUARDS
    # -------------------------------------------------------------
    # G2 (Rear Corner Light Guard Plates with Recessed Oval LED Cutout)
    # 3/16" plate, 6" x 8" formed box guard with 6.75" x 2.50" oval cutout
    g2_mat = MATERIAL_LIBRARY["3/16 Plate"]
    g2_wt = (6.0 * 8.0 * 0.1875 - 6.75 * 2.50 * 0.1875) * g2_mat["density_lb_in3"]
    plates.append(Plate(
        piece_mark="G2-L",
        description="Rear Light Guard & Corner Box - Left",
        thickness=0.1875,
        width=6.00,
        length=8.00,
        profile_pts=[(0, 0), (8, 0), (8, 6), (0, 6)],
        holes=[Hole(
            diameter=2.50,
            center_x=4.00,
            center_y=3.00,
            reference_datum="PLATE_EDGE",
            note="6.75\" x 2.50\" standard oval grommet cutout for 6\" recessed LED stop/turn/tail lamp"
        )],
        grade=g2_mat["grade"],
        material="3/16\" Steel Plate",
        quantity=1,
        unit_weight=round(g2_wt, 2),
        total_weight=round(g2_wt, 2),
        assembly="DETAILS",
        cut_notes="CNC plasma / laser cut oval opening. Steel extends 1.5\" rearward of lens to protect lamp.",
        status=StatusEnum.DESIGN
    ))
    plates.append(Plate(
        piece_mark="G2-R",
        description="Rear Light Guard & Corner Box - Right",
        thickness=0.1875,
        width=6.00,
        length=8.00,
        profile_pts=[(0, 0), (8, 0), (8, 6), (0, 6)],
        holes=[Hole(
            diameter=2.50,
            center_x=4.00,
            center_y=3.00,
            reference_datum="PLATE_EDGE",
            note="6.75\" x 2.50\" standard oval grommet cutout for 6\" recessed LED stop/turn/tail lamp"
        )],
        grade=g2_mat["grade"],
        material="3/16\" Steel Plate",
        quantity=1,
        unit_weight=round(g2_wt, 2),
        total_weight=round(g2_wt, 2),
        assembly="DETAILS",
        cut_notes="CNC plasma / laser cut oval opening. Steel extends 1.5\" rearward of lens to protect lamp.",
        status=StatusEnum.DESIGN
    ))
    
    # G3 (Ramp Hinge Mounting Ears)
    # 3/8" plate, 2.5" x 4.5" with 0.781" hole
    g3_mat = MATERIAL_LIBRARY["3/8 Plate"]
    g3_wt = (2.5 * 4.5 * 0.375) * g3_mat["density_lb_in3"]
    for i in range(1, 5):
        plates.append(Plate(
            piece_mark=f"G3-{i}",
            description=f"Hinge Mounting Ear Bracket ({i}/4)",
            thickness=0.375,
            width=2.50,
            length=4.50,
            holes=[Hole(
                diameter=0.781,
                center_x=2.25,
                center_y=1.25,
                reference_datum="BRACKET_BASE",
                note="25/32\" (0.781\") hole for 3/4\" hinge pin clearance (+1/32\")"
            )],
            grade=g3_mat["grade"],
            material="3/8\" Steel Plate",
            quantity=1,
            unit_weight=round(g3_wt, 2),
            total_weight=round(g3_wt, 2),
            assembly="DETAILS",
            cut_notes="Radius top corners 1.25\" R. Drill 25/32\" hole centered on radius.",
            status=StatusEnum.DESIGN
        ))
        
    # G4 (Front Restraint & Chain Tie-Down Plate)
    # 3/8" plate, 4" x 5" with 1.00" shackle hole
    g4_mat = MATERIAL_LIBRARY["3/8 Plate"]
    g4_wt = (4.0 * 5.0 * 0.375) * g4_mat["density_lb_in3"]
    plates.append(Plate(
        piece_mark="G4",
        description="Front Chain Tie-Down Bracket",
        thickness=0.375,
        width=4.00,
        length=5.00,
        holes=[Hole(
            diameter=1.00,
            center_x=2.50,
            center_y=2.00,
            reference_datum="BRACKET_BASE",
            note="1.00\" diameter hole for 1/2\" anchor shackle / transport grade 70 binder chain"
        )],
        grade=g4_mat["grade"],
        material="3/8\" Steel Plate",
        quantity=1,
        unit_weight=round(g4_wt, 2),
        total_weight=round(g4_wt, 2),
        assembly="DETAILS",
        cut_notes="Chamfer corners 1.0\" x 45-deg. Weld centrally to C1 header beam.",
        status=StatusEnum.DESIGN
    ))
    
    # G5 (Front Wheel Stop Angles)
    # 2x2x1/4 Angle, 12" long (Qty 2) across front of left and right tracks
    g5_mat = MATERIAL_LIBRARY["2x2x1/4 Angle"]
    g5_wt = (12.0 / 12.0) * g5_mat["wt_per_ft"]
    members.append(Member(
        piece_mark="G5-L",
        description="Front Wheel Stop Angle - Left",
        section="2x2x1/4 Angle",
        grade=g5_mat["grade"],
        length=12.00,
        quantity=1,
        start_pt=Point3D(x=2.0, y=-19.0, z=0.0),
        end_pt=Point3D(x=2.0, y=-7.0, z=0.0),
        orientation="Y",
        assembly="DETAILS",
        cut_type="SQUARE",
        unit_weight=g5_mat["wt_per_ft"],
        total_weight=round(g5_wt, 2),
        notes="Leg up, welded across left wheel track at X = 2.0\" as front tire chock.",
        status=StatusEnum.DESIGN
    ))
    members.append(Member(
        piece_mark="G5-R",
        description="Front Wheel Stop Angle - Right",
        section="2x2x1/4 Angle",
        grade=g5_mat["grade"],
        length=12.00,
        quantity=1,
        start_pt=Point3D(x=2.0, y=7.0, z=0.0),
        end_pt=Point3D(x=2.0, y=19.0, z=0.0),
        orientation="Y",
        assembly="DETAILS",
        cut_type="SQUARE",
        unit_weight=g5_mat["wt_per_ft"],
        total_weight=round(g5_wt, 2),
        notes="Leg up, welded across right wheel track at X = 2.0\" as front tire chock.",
        status=StatusEnum.DESIGN
    ))

    # -------------------------------------------------------------
    # 6. ASSEMBLE COMPLETE BOM AND CUT LIST
    # -------------------------------------------------------------
    bom_rows: List[BomRow] = []
    cut_list_rows: List[CutListRow] = []
    total_carrier_weight = 0.0
    
    # Process Members
    for m in members:
        total_carrier_weight += m.total_weight
        bom_rows.append(BomRow(
            piece_mark=m.piece_mark,
            description=m.description,
            assembly=m.assembly,
            shape=m.section.split(" ")[0],
            size=m.section,
            grade=m.grade,
            cut_length=m.length,
            quantity=m.quantity,
            unit_weight=m.unit_weight,
            total_weight=m.total_weight,
            notes=m.notes
        ))
        cut_notes = f"{m.cut_type}"
        if m.cut_angle_right != 0:
            cut_notes += f" (Right end cut @ {m.cut_angle_right:.1f} deg)"
        if m.notes:
            cut_notes += f" - {m.notes}"
        cut_list_rows.append(CutListRow(
            piece_mark=m.piece_mark,
            section=m.section,
            cut_length=m.length,
            quantity=m.quantity,
            cut_type=m.cut_type,
            cut_angle_left=m.cut_angle_left,
            cut_angle_right=m.cut_angle_right,
            notes=cut_notes
        ))
        
    # Process Plates
    for p in plates:
        total_carrier_weight += p.total_weight
        bom_rows.append(BomRow(
            piece_mark=p.piece_mark,
            description=p.description,
            assembly=p.assembly,
            shape="PLATE",
            size=f"{p.thickness}\" Thk x {p.width:.1f}\" x {p.length:.1f}\"",
            grade=p.grade,
            cut_length=p.length,
            quantity=p.quantity,
            unit_weight=p.unit_weight,
            total_weight=p.total_weight,
            notes=p.cut_notes
        ))
        cut_list_rows.append(CutListRow(
            piece_mark=p.piece_mark,
            section=p.material,
            cut_length=p.length,
            quantity=p.quantity,
            cut_type="PLATE_PROFILE",
            notes=f"Cut size {p.width:.1f}\" x {p.length:.1f}\" - {p.cut_notes}"
        ))
        
    # Structural calculations
    structural_results = calculate_structural_checks(params, total_carrier_weight)
    
    # Calculate deployed ramp angle
    # Hinge height = params.deck_height (17.0"), Ramp length = 61.0"
    ramp_angle_deg = round(math.degrees(math.asin(min(1.0, params.deck_height / params.ramp_length))), 1)

    return {
        "parameters": params,
        "provenance": get_project_provenance(params),
        "members": members,
        "plates": plates,
        "welds": welds,
        "bom": [b.model_dump() for b in bom_rows],
        "cut_list": [c.model_dump() for c in cut_list_rows],
        "total_carrier_weight": round(total_carrier_weight, 1),
        "structural": structural_results.model_dump(),
        "ramp_angle_deg": ramp_angle_deg
    }
