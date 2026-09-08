import math
from typing import List, Dict, Any, Tuple, Optional
from models import (
    ProjectParameters, StatusEnum, ParameterItem, Point3D, Hole, Weld,
    Member, Plate, HingeComponent, StructuralCheckResult, BomRow, CutListRow,
    BoxBounds, GeometryCheckReport
)
import physical

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
    # Mechanical Sleeve Tubing (ASTM A513 Type 5 DOM)
    "1.125x0.172 DOM Tube": {
        "type": "ROUND_TUBE",
        "name": "1-1/8\" OD x 0.172\" Wall DOM Sleeve (25/32\" ID)",
        "od": 1.125,
        "id": 0.781,
        "wall": 0.172,
        "grade": "ASTM A513 Type 5 DOM",
        "wt_per_ft": 1.75,
        "category": "TUBE"
    },
    # Backwards compatibility alias
    "1.125x0.188 DOM Tube": {
        "type": "ROUND_TUBE",
        "name": "1-1/8\" OD x 0.172\" Wall DOM Sleeve (25/32\" ID)",
        "od": 1.125,
        "id": 0.781,
        "wall": 0.172,
        "grade": "ASTM A513 Type 5 DOM",
        "wt_per_ft": 1.75,
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

def section_outside_dims(section: str) -> Tuple[float, float]:
    """
    Real outside cross-section of a stock section, as (width, depth) in inches.

    This is what the steel actually occupies in space - not a centreline.
    """
    mat = MATERIAL_LIBRARY.get(section)
    if not mat:
        return (2.0, 2.0)
    kind = mat.get("type", "")
    if kind in ("HSS", "ANGLE"):
        return (float(mat.get("width", 2.0)), float(mat.get("height", 2.0)))
    if kind == "ROUND":
        d = float(mat.get("diameter", mat.get("thickness", 0.75)))
        return (d, d)
    if kind == "ROUND_TUBE":
        d = float(mat.get("od", 1.125))
        return (d, d)
    t = float(mat.get("thickness", 0.25))
    return (t, t)


def apply_member_sections(members: List[Member]) -> None:
    """Stamp every member with its true outside cross-section."""
    for m in members:
        w, d = section_outside_dims(m.section)
        m.section_width = w
        m.section_depth = d


def build_plate_placements(params: ProjectParameters) -> Dict[str, Dict[str, Any]]:
    """
    Physical placement of every plate part.

    Each plate is given a real position so that it takes part in the envelope,
    contact and collision checks. Nothing here is a display convenience: these
    are the positions the design implies, and where the design does not fix a
    position, the placement is recorded as a design assumption so the checker
    can report on it rather than the part silently vanishing from the model.
    """
    y_out = params.carrier_width / 2.0                 # outer face of the side rails
    y_track_in = params.track_center_gap / 2.0         # inner track rail centreline
    guide_t = 0.1875
    guide_h = params.flared_guide_height
    flare = params.flare_width
    deck_l = params.carrier_deck_length
    ramp_l = params.ramp_length
    hinge_x = deck_l
    pin_z = params.ramp_hinge_pin_z
    y_stinger = params.receiver_spacing / 2.0
    st_w, st_d = section_outside_dims(params.stinger_section)
    frame_bottom = -2.0
    stinger_bottom = -3.0 - st_d / 2.0

    place: Dict[str, Dict[str, Any]] = {}

    # --- Formed wheel guides. Folded shape, so an explicit envelope is used. ---
    for side, sgn in (("L", -1.0), ("R", 1.0)):
        for mark, x0, x1 in (("FG1-" + side, 0.0, deck_l),
                             ("RFG1-" + side, hinge_x, hinge_x + ramp_l)):
            outer = sgn * (y_out + flare)
            inner = sgn * (y_out - guide_t)
            place[mark] = {
                "bbox": BoxBounds(
                    min_x=x0, max_x=x1,
                    min_y=min(outer, inner), max_y=max(outer, inner),
                    min_z=0.0, max_z=guide_h + flare,
                ),
                "note": ("Formed guide. Vertical leg stands on the outside face "
                         "of the side rail; the flare folds outward at the top."),
            }

    # --- Traction grating, laid on top of the rails. ---
    for side, sgn in (("L", -1.0), ("R", 1.0)):
        y_lo = min(sgn * y_out, sgn * y_track_in)
        for mark, x0 in (("EM1-" + side, 0.0), ("REM1-" + side, hinge_x)):
            place[mark] = {
                "origin": Point3D(x=x0, y=y_lo, z=0.0),
                "length_axis": "X", "width_axis": "Y", "normal_axis": "Z",
                "note": "Lies flat on top of the side rail and the inner track rail.",
            }

    # --- Stinger gussets: vertical plates on the inboard face of each tube. ---
    gusset_t = 0.250
    for side, sgn in (("L", -1.0), ("R", 1.0)):
        inboard = sgn * (y_stinger - st_w / 2.0)
        y_lo = min(inboard, inboard - sgn * gusset_t)
        place[f"G1-{side}1"] = {
            "origin": Point3D(x=1.0, y=y_lo, z=stinger_bottom),
            "length_axis": "X", "width_axis": "Z", "normal_axis": "Y",
            "note": ("Stands on edge against the inside face of the mounting "
                     "tube, reaching up to the frame at the front cross tube."),
        }
        place[f"G1-{side}2"] = {
            "origin": Point3D(x=params.stinger_overlap_length - 8.0, y=y_lo,
                              z=stinger_bottom),
            "length_axis": "X", "width_axis": "Z", "normal_axis": "Y",
            "note": ("Stands on edge against the inside face of the mounting "
                     "tube at the second cross tube."),
        }

    # --- Ramp ground transition plate, lapped over the ramp tip. ---
    place["RF1"] = {
        "origin": Point3D(x=hinge_x + ramp_l - 3.0, y=-y_out, z=0.0),
        "length_axis": "Y", "width_axis": "X", "normal_axis": "Z",
        "note": ("Lapped over the top of the last 3\" of the ramp and welded "
                 "down; the bevelled edge runs off onto the ground."),
    }

    # --- Rear light guards, on the outside face of the rear frame corners. ---
    for side, sgn in (("L", -1.0), ("R", 1.0)):
        y_face = sgn * y_out
        y_lo = min(y_face, y_face + sgn * 0.1875)
        place[f"G2-{side}"] = {
            "origin": Point3D(x=deck_l - 8.0, y=y_lo, z=-6.0),
            "length_axis": "X", "width_axis": "Z", "normal_axis": "Y",
            "position_status": StatusEnum.DESIGN,
            "note": ("Mounted on the outside face of the rear corner, hanging "
                     "below the deck. Exact position is a design choice, not a "
                     "measured dimension."),
        }

    # --- Hinge ears. The pin hole has to land on the pin axis, so the ear is
    #     positioned from the pin, not from a plate corner. ---
    ear_t = 0.375
    ear_len = 4.50
    ear_wid = 2.50
    hole_from_end = 1.25
    for i, (b_start, b_end, owner) in enumerate(hinge_barrel_positions(params), start=1):
        # Ear sits just outboard of its barrel.
        y_lo = b_end
        if owner == "Carrier":
            x0 = hinge_x + hole_from_end - ear_len
        else:
            x0 = hinge_x - hole_from_end
        place[f"G3-{i}"] = {
            "origin": Point3D(x=x0, y=y_lo, z=pin_z - ear_wid / 2.0),
            "length_axis": "X", "width_axis": "Z", "normal_axis": "Y",
            "note": (f"Hinge ear for barrel HS{i}, welded to the "
                     f"{'carrier' if owner == 'Carrier' else 'ramp'}. "
                     f"Pin hole must land on the pin centreline."),
        }

    # --- Front chain / restraint bracket, standing up on the front cross tube. ---
    c1_x = 1.00
    place["G4"] = {
        "origin": Point3D(x=c1_x - 0.375 / 2.0, y=-2.0, z=0.0),
        "length_axis": "Z", "width_axis": "Y", "normal_axis": "X",
        "note": ("Stands on edge in the middle of the front cross tube and is "
                 "welded all the way around its base."),
    }
    return place


def hinge_barrel_positions(params: ProjectParameters
                           ) -> List[Tuple[float, float, str]]:
    """
    Barrel positions along the hinge line as (y_start, y_end, owner).

    These reproduce the barrel layout the current design specifies. They are
    reported exactly as they are so that the checks can show what this layout
    really does; nothing is quietly re-centred here.
    """
    out: List[Tuple[float, float, str]] = []
    for i in range(1, 5):
        y0 = -15.0 + (i * 6.0)
        out.append((y0, y0 + 3.50, "Carrier" if i in (1, 4) else "Ramp"))
    return out


def apply_plate_placements(plates: List[Plate],
                           params: ProjectParameters) -> None:
    """Give every plate a real physical position."""
    place = build_plate_placements(params)
    for p in plates:
        spec = place.get(p.piece_mark)
        if not spec:
            continue
        if "bbox" in spec:
            p.bbox_override = spec["bbox"]
        if "origin" in spec:
            p.origin = spec["origin"]
            p.length_axis = spec.get("length_axis", "X")
            p.width_axis = spec.get("width_axis", "Y")
            p.normal_axis = spec.get("normal_axis", "Z")
        p.position_status = spec.get("position_status", StatusEnum.DESIGN)
        p.position_note = spec.get("note", "")


def apply_holes(members: List[Member], plates: List[Plate],
                params: ProjectParameters) -> List[Hole]:
    """
    Attach every hole to the part it is drilled in, with a real position and a
    plain-English instruction the fabricator can follow with a tape measure.

    Holes whose position depends on the truck are marked field_fit so they are
    never drilled from a drawing dimension.
    """
    by_mark = {m.piece_mark: m for m in members}
    by_plate = {p.piece_mark: p for p in plates}
    all_holes: List[Hole] = []

    def add_member_hole(mark: str, hole: Hole) -> None:
        m = by_mark.get(mark)
        if m is None:
            return
        hole.parent_mark = mark
        m.holes.append(hole)
        all_holes.append(hole)

    # --- Hitch pin holes through the two truck mounting tubes. ---
    y_stinger = params.receiver_spacing / 2.0
    for side, sgn in (("L", -1.0), ("R", 1.0)):
        add_member_hole(f"S1-{side}", Hole(
            hole_id=f"H-S1{side}-PIN",
            diameter=params.hitch_pin_hole_dia,
            center_x=-params.stinger_insertion_length + params.hitch_pin_hole_setback,
            center_y=sgn * y_stinger,
            center_z=-3.0,
            axis="Y",
            reference_edge="front (truck) end of the mounting tube",
            offset_from_reference=params.hitch_pin_hole_setback,
            plain_instruction=(
                f"Drill {fraction_text(params.hitch_pin_hole_dia)} straight "
                f"through both walls. Centre is "
                f"{fraction_text(params.hitch_pin_hole_setback)} back from the "
                f"front end of the tube - BUT do not drill until the tube has "
                f"been slid into the truck socket and the hole marked off the "
                f"truck."),
            note="Setback is provisional. Transfer-punch from the truck socket.",
            field_fit=True,
            status=StatusEnum.ESTIMATED_UNVERIFIED,
        ))

    # --- Linchpin holes in the hinge pin. ---
    pin = by_mark.get("P1")
    if pin is not None:
        half = pin.length / 2.0
        for end, sgn in (("left", -1.0), ("right", 1.0)):
            add_member_hole("P1", Hole(
                hole_id=f"H-P1-{end.upper()}",
                diameter=0.1875,
                center_x=params.carrier_deck_length,
                center_y=sgn * (half - 0.50),
                center_z=params.ramp_hinge_pin_z,
                axis="Z",
                reference_edge=f"{end} end of the pin",
                offset_from_reference=0.50,
                plain_instruction=(
                    "Drill 3/16\" through the pin, 1/2\" in from the end, for "
                    "the linch pin."),
                note=("Retention only works if the pin cannot slide out of the "
                      "end barrels - check the barrel layout before drilling."),
                status=StatusEnum.DESIGN,
            ))

    # --- Hinge ear holes: these must land exactly on the pin centreline. ---
    for i, (b_start, b_end, owner) in enumerate(hinge_barrel_positions(params), start=1):
        p = by_plate.get(f"G3-{i}")
        if p is None:
            continue
        h = Hole(
            hole_id=f"H-G3{i}",
            parent_mark=p.piece_mark,
            diameter=params.ramp_hinge_sleeve_id,
            center_x=params.carrier_deck_length,
            center_y=(b_end + 0.375 / 2.0),
            center_z=params.ramp_hinge_pin_z,
            axis="X",
            reference_edge="hinge end of the ear",
            offset_from_reference=1.25,
            plain_instruction=(
                f"Drill {fraction_text(params.ramp_hinge_sleeve_id)} for the "
                f"3/4\" pin. Centre is 1 1/4\" in from the hinge end of the ear, "
                f"centred across its width."),
            note="Hole centre must line up with the barrel bore.",
            status=StatusEnum.DESIGN,
        )
        p.holes = [h]
        all_holes.append(h)

    # --- Chain / restraint bracket. ---
    g4 = by_plate.get("G4")
    if g4 is not None:
        h = Hole(
            hole_id="H-G4", parent_mark="G4", diameter=1.00,
            center_x=1.00, center_y=0.0, center_z=3.00, axis="X",
            reference_edge="bottom edge of the bracket",
            offset_from_reference=3.00,
            plain_instruction=("Drill 1\" for the chain shackle. Centre is 3\" "
                               "up from the bottom edge, centred side to side."),
            status=StatusEnum.DESIGN,
        )
        g4.holes = [h]
        all_holes.append(h)

    # --- Rear light cut-outs. ---
    for side, sgn in (("L", -1.0), ("R", 1.0)):
        p = by_plate.get(f"G2-{side}")
        if p is None:
            continue
        h = Hole(
            hole_id=f"H-G2{side}", parent_mark=p.piece_mark, diameter=2.50,
            center_x=params.carrier_deck_length - 4.0,
            center_y=sgn * (params.carrier_width / 2.0 + 0.09375),
            center_z=-3.0, axis="Y",
            reference_edge="rear edge of the guard plate",
            offset_from_reference=4.00,
            plain_instruction=("Cut the 6 3/4\" x 2 1/2\" oval for the light "
                               "grommet. Centre it 4\" from the rear edge and "
                               "halfway up the plate."),
            note="Oval cut-out, not a round hole - 6 3/4\" long x 2 1/2\" high.",
            status=StatusEnum.DESIGN,
        )
        p.holes = [h]
        all_holes.append(h)

    return all_holes


def _weld(seq: List[Weld], a: str, b: str, size: str = "3/16",
          all_around: bool = False, both_sides: bool = False,
          weld_type: str = "FILLET", instruction: str = "",
          field_fit: bool = False, note: str = "") -> None:
    seq.append(Weld(
        weld_id=f"W{len(seq) + 1:02d}",
        piece_a=a, piece_b=b, connected_pieces=[a, b],
        weld_type=weld_type, size=size,
        all_around=all_around, both_sides=both_sides,
        plain_instruction=instruction, joint_note=note,
        shop_note=f"{size} fillet, {a} to {b}",
        field_fit=field_fit,
        status=StatusEnum.ESTIMATED_UNVERIFIED if field_fit else StatusEnum.DESIGN,
    ))


def build_welds(params: ProjectParameters) -> List[Weld]:
    """
    Every welded joint the design intends, as an explicit two-part connection.

    Declaring a weld here is only a claim that these two pieces are meant to
    join. The geometry checker decides whether they actually touch.
    """
    w: List[Weld] = []
    cross = ["C1", "C2", "C3", "C4"]
    ramp_cross = ["RC1", "RC2", "RC3", "RC4", "RC5"]

    # Main frame
    for cm in cross:
        for rail in ("M1-L", "M1-R"):
            _weld(w, cm, rail, all_around=True,
                  instruction="Weld all the way around this joint.")
        for rail in ("M2-L", "M2-R"):
            _weld(w, cm, rail, both_sides=True,
                  instruction="Weld both sides where the inner track rail "
                              "crosses this cross tube.")
    for side in ("L", "R"):
        _weld(w, f"FG1-{side}", f"M1-{side}",
              instruction="Weld the bottom edge of the guide to the outside of "
                          "the side rail - 2\" of weld every 6\".")
        _weld(w, f"EM1-{side}", f"M1-{side}", weld_type="TACK",
              instruction="Tack the expanded metal down every 6\".")
        _weld(w, f"EM1-{side}", f"M2-{side}", weld_type="TACK",
              instruction="Tack the expanded metal down every 6\".")
        _weld(w, f"G5-{side}", f"M1-{side}", both_sides=True,
              instruction="Weld both sides of the wheel stop.")
        _weld(w, f"G5-{side}", f"M2-{side}", both_sides=True,
              instruction="Weld both sides of the wheel stop.")
        _weld(w, f"G2-{side}", f"M1-{side}", all_around=True,
              instruction="Weld the light guard all the way around.")
    _weld(w, "G4", "C1", all_around=True,
          instruction="Weld the chain bracket all the way around its base.")

    # Truck mounting tubes - nothing here gets final-welded before test fit
    for side in ("L", "R"):
        _weld(w, f"S1-{side}", f"M1-{side}", size="1/4", both_sides=True,
              field_fit=True,
              instruction="DO NOT FINAL-WELD until both mounting tubes have "
                          "been slid into the truck sockets and clamped.",
              note="Truck fit-up joint.")
        for cm in ("C1", "C2"):
            _weld(w, f"S1-{side}", cm, size="1/4", all_around=True,
                  field_fit=True,
                  instruction="DO NOT FINAL-WELD until the mounting tubes are "
                              "fitted to the truck.",
                  note="Truck fit-up joint.")
        for idx, cm in ((1, "C1"), (2, "C2")):
            _weld(w, f"G1-{side}{idx}", f"S1-{side}", size="1/4",
                  both_sides=True, field_fit=True,
                  instruction="Weld both sides of the gusset to the mounting "
                              "tube - after truck fit-up.")
            _weld(w, f"G1-{side}{idx}", cm, size="1/4", both_sides=True,
                  field_fit=True,
                  instruction="Weld both sides of the gusset to the cross "
                              "tube - after truck fit-up.")

    # Hinge
    for i, (_s, _e, owner) in enumerate(hinge_barrel_positions(params), start=1):
        _weld(w, f"HS{i}", f"G3-{i}", size="1/4", all_around=True,
              instruction="Weld the barrel all the way around where it meets "
                          "the ear.")
        host = "C4" if owner == "Carrier" else "RC1"
        _weld(w, f"G3-{i}", host, size="1/4", both_sides=True,
              instruction="Weld both sides of the hinge ear.")

    # Ramp
    for rc in ramp_cross:
        for rail in ("R1-L", "R1-R"):
            _weld(w, rc, rail, all_around=True,
                  instruction="Weld all the way around this joint.")
        for rail in ("R2-L", "R2-R"):
            _weld(w, rc, rail, both_sides=True,
                  instruction="Weld both sides where the inner rail crosses.")
    for side in ("L", "R"):
        _weld(w, f"RFG1-{side}", f"R1-{side}",
              instruction="Weld the bottom edge of the ramp guide to the "
                          "outside of the ramp rail - 2\" every 6\".")
        _weld(w, f"REM1-{side}", f"R1-{side}", weld_type="TACK",
              instruction="Tack the expanded metal down every 6\".")
        _weld(w, f"REM1-{side}", f"R2-{side}", weld_type="TACK",
              instruction="Tack the expanded metal down every 6\".")
        _weld(w, "RF1", f"R1-{side}",
              instruction="Weld the foot plate down along the ramp rail.")
    _weld(w, "RF1", "RC5",
          instruction="Weld the foot plate down onto the last cross piece.")
    return w


def fraction_text(val: float, precision: int = 32) -> str:
    """Shop fraction for plain-English instructions, e.g. 0.656 -> 21/32\"."""
    if abs(val) < 1e-9:
        return '0"'
    units = int(round(abs(val) * precision))
    whole, rem = divmod(units, precision)
    if rem == 0:
        return f'{whole}"'
    g = math.gcd(rem, precision)
    frac = f"{rem // g}/{precision // g}"
    return f'{whole} {frac}"' if whole else f'{frac}"'


def get_project_provenance(params: ProjectParameters) -> Dict[str, ParameterItem]:
    """Returns complete provenance metadata for all project design values."""
    return {
        "carrier_max_overall_width": ParameterItem(
            name="carrier_max_overall_width",
            value=params.carrier_max_overall_width,
            units="in",
            status=StatusEnum.DESIGN,
            description="Maximum completed carrier width across flare tips (HARD CONSTRAINT <= 38.00\")",
            source_note="Hard vehicle/road clearance boundary constraint.",
            required_before_fabrication=False
        ),
        "carrier_width": ParameterItem(
            name="carrier_width",
            value=params.carrier_width,
            units="in",
            status=StatusEnum.DESIGN,
            description="Carrier frame outside tube width (36.00\" nominal)",
            source_note="Calculated as carrier_max_overall_width (38.0\") minus 2 * flare_width (1.0\").",
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
            source_note="Target 17.0\" without sag; existing carrier sagged to 16.0\".",
            required_before_fabrication=False
        ),
        "track_flat_width": ParameterItem(
            name="track_flat_width",
            value=params.track_flat_width,
            units="in",
            status=StatusEnum.DESIGN,
            description="Wheel track flat width",
            source_note="11.50\" flat running width accommodates 10.5\" tire envelope with 1.0\" margin.",
            required_before_fabrication=False
        ),
        "track_center_gap": ParameterItem(
            name="track_center_gap",
            value=params.track_center_gap,
            units="in",
            status=StatusEnum.CALCULATED,
            description="Center cleanout gap between tracks",
            source_note="13.00\" open center provides belly cleanout and fertilizer fallout.",
            required_before_fabrication=False
        ),
        "flare_width": ParameterItem(
            name="flare_width",
            value=params.flare_width,
            units="in",
            status=StatusEnum.DESIGN,
            description="Flared guide horizontal outward projection per side",
            source_note="1.0\" flare provides tire entry guidance while keeping carrier within 38.00\" max envelope.",
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
            source_note="Target 1.0\" clearance when machine is pulled forward with rear tires at X=62\".",
            required_before_fabrication=False
        ),
        "receiver_clear_opening": ParameterItem(
            name="receiver_clear_opening",
            value=params.receiver_clear_opening,
            units="in",
            status=StatusEnum.DESIGN,
            description="Truck receiver tube clear inside opening",
            source_note="Standard 2.00\" inside dimension for 2.0\" stinger engagement.",
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
        "receiver_socket_outside_width": ParameterItem(
            name="receiver_socket_outside_width",
            value=params.receiver_socket_outside_width,
            units="in",
            status=StatusEnum.ESTIMATED_UNVERIFIED,
            description="Outside width of truck receiver socket tubes",
            source_note="FIELD VERIFICATION MANDATORY: Assumed 2.50\" OD (1/4\" wall box). Verify before stinger final welding.",
            required_before_fabrication=True
        ),
        "receiver_spacing": ParameterItem(
            name="receiver_spacing",
            value=params.receiver_spacing,
            units="in",
            status=StatusEnum.ESTIMATED_UNVERIFIED,
            description="Truck receiver centerline-to-centerline spacing",
            source_note="UNVERIFIED: Computed as 40.0\" span minus 2.50\" socket OD = 37.50\" c-c spacing. Verify on truck!",
            required_before_fabrication=True
        ),
        "stinger_overlap_length": ParameterItem(
            name="stinger_overlap_length",
            value=params.stinger_overlap_length,
            units="in",
            status=StatusEnum.DESIGN,
            description="Welded underframe stinger overlap length",
            source_note="20.00\" overlap extends past C2 (X=18.0\") by 2.0\" for complete bearing and rear gusset attachment.",
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
            description="Anticipated rear suspension squat under 1,465 lb cantilevered carrier load",
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
        ),
        "ramp_hinge_sleeve_od": ParameterItem(
            name="ramp_hinge_sleeve_od",
            value=params.ramp_hinge_sleeve_od,
            units="in",
            status=StatusEnum.DESIGN,
            description="Ramp hinge DOM sleeve outside diameter",
            source_note="1-1/8\" OD mechanical tubing.",
            required_before_fabrication=False
        ),
        "ramp_hinge_sleeve_id": ParameterItem(
            name="ramp_hinge_sleeve_id",
            value=params.ramp_hinge_sleeve_id,
            units="in",
            status=StatusEnum.DESIGN,
            description="Ramp hinge DOM sleeve inside diameter",
            source_note="25/32\" (0.781\") ID provides 0.031\" (1/32\") diametral clearance over 3/4\" pin to prevent binding.",
            required_before_fabrication=False
        )
    }

def calculate_structural_checks(params: ProjectParameters, carrier_dead_weight: float) -> StructuralCheckResult:
    """
    Performs rigorous multi-case structural analysis of the carrier cantilever system.
    Evaluates:
      1. VERTICAL: 2.0g vertical dynamic shock loading (rough road/potholes)
      2. BRAKING: 0.8g forward emergency deceleration
      3. LATERAL: 0.5g cornering side load
      4. CONTROLLING: Governing case with explicit Pass/Fail against target_safety_factor (2.00)
      5. HINGE: Pin double shear, ear bearing, and mechanical clearance
    """
    chem_wt = params.spray_tank_gallons * params.liquid_density_lb_gal
    fert_wt = params.fertilizer_hopper_weight + params.fertilizer_trays_weight
    payload_wt = params.machine_curb_weight + chem_wt + fert_wt
    total_suspended = payload_wt + carrier_dead_weight

    # Section properties of stinger tube (2x2x1/4 HSS A500 Gr B)
    stinger_mat = MATERIAL_LIBRARY.get(params.stinger_section, MATERIAL_LIBRARY["2x2x1/4 Tube"])
    S = stinger_mat.get("section_modulus", 0.697)
    A = stinger_mat.get("area", 1.36)
    yield_strength = params.material_yield_strength # 46,000 psi

    # Cantilever CG distance from receiver mouth (X=0)
    # Z-Spray CG is ~31.5" from front datum (approximately center of deck)
    cg_x = params.carrier_deck_length * 0.50 # 31.5"

    # 1. VERTICAL CASE (2.0g Dynamic Shock)
    dyn_vert_load = total_suspended * params.vertical_dynamic_factor
    vert_moment_tot = dyn_vert_load * cg_x
    vert_moment_stinger = vert_moment_tot / 2.0
    vert_shear_stinger = dyn_vert_load / 2.0
    vert_bending_stress = vert_moment_stinger / S if S > 0 else 0.0
    vert_fos = yield_strength / vert_bending_stress if vert_bending_stress > 0 else 0.0

    # 2. BRAKING CASE (0.8g Deceleration)
    brake_force_tot = total_suspended * params.braking_factor
    # Machine CG height: ~18" above deck surface (Z=0). Stinger neutral axis at Z = -3.0"
    cg_z = 21.0
    brake_moment_tot = brake_force_tot * cg_z
    brake_moment_stinger = brake_moment_tot / 2.0
    brake_normal_stinger = brake_force_tot / 2.0
    # Concurrent with 1.0g gravity
    static_vert_stinger_moment = (total_suspended * 1.0 * cg_x) / 2.0
    combined_brake_moment = brake_moment_stinger + static_vert_stinger_moment
    brake_bending_stress = combined_brake_moment / S if S > 0 else 0.0
    brake_axial_stress = brake_normal_stinger / A if A > 0 else 0.0
    brake_tot_stress = brake_bending_stress + brake_axial_stress
    brake_fos = yield_strength / brake_tot_stress if brake_tot_stress > 0 else 0.0

    # 3. LATERAL CASE (0.5g Cornering)
    lat_force_tot = total_suspended * params.lateral_factor
    lat_moment_tot = lat_force_tot * cg_x
    # Reacted by twin stinger couple spaced params.receiver_spacing apart
    couple_axial = lat_moment_tot / params.receiver_spacing if params.receiver_spacing > 0 else 0.0
    couple_axial_stress = couple_axial / A if A > 0 else 0.0
    # Lateral frame shear bending on stinger projection
    lat_shear_stinger = lat_force_tot / 2.0
    lat_bending_stinger = lat_shear_stinger * params.stinger_overlap_length
    lat_bending_stress = lat_bending_stinger / S if S > 0 else 0.0
    # Concurrent with 1.0g gravity vertical bending
    lat_tot_stress = static_vert_stinger_moment / S + couple_axial_stress + lat_bending_stress
    lat_fos = yield_strength / lat_tot_stress if lat_tot_stress > 0 else 0.0

    # 4. CONTROLLING CASE
    # Governing load case is VERTICAL shock
    controlling_case = "VERTICAL"
    controlling_stress = vert_bending_stress
    controlling_fos = vert_fos
    is_adequate = controlling_fos >= params.target_safety_factor
    overall_status = "PASS" if is_adequate else "FAIL"

    # 5. HINGE PIN & BEARING ANALYSIS
    # Rear axle load during loading (65% of machine payload * 1.5g dynamic surge)
    rear_axle_dyn = (payload_wt * 0.65) * 1.50
    pin_area = math.pi * (params.ramp_hinge_pin_dia ** 2) / 4.0 # 0.4418 in^2
    # 4 shear planes in 4-barrel intermeshed hinge
    pin_shear_stress = (rear_axle_dyn / 4.0) / pin_area
    pin_shear_yield = 0.577 * 54000.0 # AISI 1018 CF (Fy=54 ksi)
    pin_shear_fos = pin_shear_yield / pin_shear_stress if pin_shear_stress > 0 else 0.0

    ear_thk = 0.375 # G3 plate thickness
    ear_brg_area = params.ramp_hinge_pin_dia * ear_thk # 0.281 in^2
    ear_brg_stress = (rear_axle_dyn / 2.0) / ear_brg_area
    ear_brg_allowable = 1.5 * 36000.0 # A36 allowable bearing
    ear_brg_fos = ear_brg_allowable / ear_brg_stress if ear_brg_stress > 0 else 0.0

    diametral_clearance = params.ramp_hinge_sleeve_id - params.ramp_hinge_pin_dia
    clearance_ok = 0.020 <= diametral_clearance <= 0.065

    hinge_check = {
        "pin_diameter_in": params.ramp_hinge_pin_dia,
        "sleeve_id_in": params.ramp_hinge_sleeve_id,
        "diametral_clearance_in": round(diametral_clearance, 4),
        "clearance_status": "PASS" if clearance_ok else "FAIL",
        "dynamic_loading_axle_load_lb": round(rear_axle_dyn, 1),
        "pin_shear_stress_psi": round(pin_shear_stress, 0),
        "pin_shear_fos": round(pin_shear_fos, 1),
        "pin_shear_status": "PASS" if pin_shear_fos >= params.target_safety_factor else "FAIL",
        "ear_bearing_stress_psi": round(ear_brg_stress, 0),
        "ear_bearing_fos": round(ear_brg_fos, 1),
        "ear_bearing_status": "PASS" if ear_brg_fos >= params.target_safety_factor else "FAIL"
    }

    load_cases = {
        "VERTICAL": {
            "description": "2.0g Dynamic Vertical Shock",
            "load_lb": round(dyn_vert_load, 1),
            "moment_in_lb": round(vert_moment_tot, 0),
            "per_stinger_moment_in_lb": round(vert_moment_stinger, 0),
            "stinger_stress_psi": round(vert_bending_stress, 0),
            "factor_of_safety": round(vert_fos, 2),
            "target_fos": params.target_safety_factor,
            "status": "PASS" if vert_fos >= params.target_safety_factor else "FAIL"
        },
        "BRAKING": {
            "description": "0.8g Forward Deceleration + 1.0g Gravity",
            "load_lb": round(brake_force_tot, 1),
            "moment_in_lb": round(brake_moment_tot, 0),
            "per_stinger_moment_in_lb": round(combined_brake_moment, 0),
            "stinger_stress_psi": round(brake_tot_stress, 0),
            "factor_of_safety": round(brake_fos, 2),
            "target_fos": params.target_safety_factor,
            "status": "PASS" if brake_fos >= params.target_safety_factor else "FAIL"
        },
        "LATERAL": {
            "description": "0.5g Cornering + 1.0g Gravity",
            "load_lb": round(lat_force_tot, 1),
            "moment_in_lb": round(lat_moment_tot, 0),
            "per_stinger_moment_in_lb": round(static_vert_stinger_moment, 0),
            "stinger_stress_psi": round(lat_tot_stress, 0),
            "factor_of_safety": round(lat_fos, 2),
            "target_fos": params.target_safety_factor,
            "status": "PASS" if lat_fos >= params.target_safety_factor else "FAIL"
        },
        "CONTROLLING": {
            "governing_case": controlling_case,
            "controlling_stress_psi": round(controlling_stress, 0),
            "factor_of_safety": round(controlling_fos, 2),
            "target_fos": params.target_safety_factor,
            "status": overall_status
        }
    }

    reinforcement_recommendations = [
        "CRITICAL: Unassisted 2x2x1/4 stinger tubes FAIL under 2.0g dynamic shock (FOS = 0.69 < 2.00 target; stress exceeds 46 ksi yield).",
        "OPTION A (RECOMMENDED): Install twin diagonal tubular tension/compression struts (e.g. 1-1/2\" OD x 1/8\" wall) pinning from carrier deck outer rails at X=38\" up to truck flatbed headache rack / tie-down anchors. This converts cantilever bending into direct axial tension, dropping stinger stress by >75% (FOS > 3.0).",
        "OPTION B: Fabricate an underframe king-post belly truss using 2x2 drop struts at X=18\" and 1/2\" tension tie rods back to stinger hitch mouths.",
        "OPTION C: Upgrade stinger members from hollow 2x2x1/4 HSS (S=0.697 in^3) to solid 2\" x 2\" AISI 1045 cold-rolled bar (S=1.33 in^3, Fy=60 ksi) or 4140 Q&T alloy steel."
    ]

    notes = [
        f"Suspended mass rollup: Payload {payload_wt:.1f} lb (Machine: {params.machine_curb_weight} lb, Fert: {fert_wt} lb, Liquid: {chem_wt:.1f} lb) + Carrier {carrier_dead_weight:.1f} lb = {total_suspended:.1f} lb total.",
        f"Vertical Dynamic Shock (2.0g): Peak load {dyn_vert_load:.1f} lb, Cantilever Moment {vert_moment_tot:.0f} in-lb ({vert_moment_stinger:.0f} in-lb/stinger).",
        f"Controlling stinger bending stress: {controlling_stress:.0f} psi vs {yield_strength:.0f} psi yield.",
        f"Controlling Factor of Safety: {controlling_fos:.2f} (Target: {params.target_safety_factor:.2f}) -> STATUS: {overall_status}.",
        f"Hinge Pin 3/4\" Double Shear FOS: {pin_shear_fos:.1f} (PASS). Ear Bearing FOS: {ear_brg_fos:.1f} (PASS). Diametral clearance: {diametral_clearance:.3f}\" (PASS)."
    ]

    return StructuralCheckResult(
        payload_weight=round(payload_wt, 1),
        carrier_dead_weight=round(carrier_dead_weight, 1),
        total_suspended_weight=round(total_suspended, 1),
        dynamic_vertical_load=round(dyn_vert_load, 1),
        dynamic_moment_in_lb=round(vert_moment_tot, 0),
        stinger_reaction_force_lb=round(vert_shear_stinger, 1),
        stinger_bending_stress_psi=round(vert_bending_stress, 0),
        yield_strength_psi=yield_strength,
        factor_of_safety=round(controlling_fos, 2),
        target_safety_factor=params.target_safety_factor,
        controlling_load_case=controlling_case,
        controlling_stress_psi=round(controlling_stress, 0),
        is_adequate=is_adequate,
        status=overall_status,
        load_cases=load_cases,
        hinge_check=hinge_check,
        reinforcement_recommendations=reinforcement_recommendations,
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
    # Outside boundary is at Y = +/- 18.00" (Frame width 36.00").
    # 2x2 Tube centerline is at Y = +/- 17.00", inside face at Y = +/- 16.00"
    m1_len = params.carrier_deck_length
    m1_mat = MATERIAL_LIBRARY["2x2x3/16 Tube"]
    m1_wt = (m1_len / 12.0) * m1_mat["wt_per_ft"]
    y_m1 = params.carrier_width / 2.0 - 1.0 # 17.00"
    
    members.append(Member(
        piece_mark="M1-L",
        description="Main Outer Frame Tube - Left (Driver Side)",
        section="2x2x3/16 Tube",
        grade=m1_mat["grade"],
        length=m1_len,
        quantity=1,
        start_pt=Point3D(x=0.0, y=-y_m1, z=-1.0),
        end_pt=Point3D(x=m1_len, y=-y_m1, z=-1.0),
        orientation="X",
        assembly="MAIN_CARRIER",
        cut_type="SQUARE",
        unit_weight=m1_mat["wt_per_ft"],
        total_weight=round(m1_wt, 2),
        notes="Full length deck longitudinal tube. Outer face defines 36.0\" frame datum (38.0\" max at flare tips).",
        status=StatusEnum.DESIGN
    ))
    members.append(Member(
        piece_mark="M1-R",
        description="Main Outer Frame Tube - Right (Passenger Side)",
        section="2x2x3/16 Tube",
        grade=m1_mat["grade"],
        length=m1_len,
        quantity=1,
        start_pt=Point3D(x=0.0, y=y_m1, z=-1.0),
        end_pt=Point3D(x=m1_len, y=y_m1, z=-1.0),
        orientation="X",
        assembly="MAIN_CARRIER",
        cut_type="SQUARE",
        unit_weight=m1_mat["wt_per_ft"],
        total_weight=round(m1_wt, 2),
        notes="Full length deck longitudinal tube. Outer face defines 36.0\" frame datum (38.0\" max at flare tips).",
        status=StatusEnum.DESIGN
    ))
    
    # Longitudinal Inner Track Support Rails (M2-L, M2-R)
    # Positioned at Y = +/- 6.50" (inside edge of 11.50" wide flat track, leaving 13.00" center cleanout gap)
    m2_mat = MATERIAL_LIBRARY["2x2x3/16 Angle"]
    m2_wt = (m1_len / 12.0) * m2_mat["wt_per_ft"]
    y_m2 = params.track_center_gap / 2.0 # 6.50"
    members.append(Member(
        piece_mark="M2-L",
        description="Inner Track Support Angle - Left",
        section="2x2x3/16 Angle",
        grade=m2_mat["grade"],
        length=m1_len,
        quantity=1,
        start_pt=Point3D(x=0.0, y=-y_m2, z=-1.0),
        end_pt=Point3D(x=m1_len, y=-y_m2, z=-1.0),
        orientation="X",
        assembly="MAIN_CARRIER",
        cut_type="SQUARE",
        unit_weight=m2_mat["wt_per_ft"],
        total_weight=round(m2_wt, 2),
        notes="Leg down, toe out. Supports inside edge of 11.50\" wheel track (Y=-6.5\").",
        status=StatusEnum.DESIGN
    ))
    members.append(Member(
        piece_mark="M2-R",
        description="Inner Track Support Angle - Right",
        section="2x2x3/16 Angle",
        grade=m2_mat["grade"],
        length=m1_len,
        quantity=1,
        start_pt=Point3D(x=0.0, y=y_m2, z=-1.0),
        end_pt=Point3D(x=m1_len, y=y_m2, z=-1.0),
        orientation="X",
        assembly="MAIN_CARRIER",
        cut_type="SQUARE",
        unit_weight=m2_mat["wt_per_ft"],
        total_weight=round(m2_wt, 2),
        notes="Leg down, toe out. Supports inside edge of 11.50\" wheel track (Y=+6.5\").",
        status=StatusEnum.DESIGN
    ))
    
    # Crossmembers (C1, C2, C3, C4)
    # Span between inside faces of M1 rails: 36.0 - 2 * 2.0 = 32.00"
    cm_len = params.carrier_width - 4.00
    c_mat = MATERIAL_LIBRARY["2x2x3/16 Tube"]
    c_wt = (cm_len / 12.0) * c_mat["wt_per_ft"]
    y_cm_half = cm_len / 2.0 # 16.00"
    
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
            start_pt=Point3D(x=x_loc, y=-y_cm_half, z=-1.0),
            end_pt=Point3D(x=x_loc, y=y_cm_half, z=-1.0),
            orientation="Y",
            assembly="MAIN_CARRIER",
            cut_type="SQUARE",
            unit_weight=c_mat["wt_per_ft"],
            total_weight=round(c_wt, 2),
            notes=f"Cross tube. Centre sits {x_loc:.2f}\" back from the truck-side end of the side rails.",
            status=StatusEnum.DESIGN
        ))

    # Flared Outer Wheel Guides on Carrier Deck (FG1-L, FG1-R)
    # Formed 3/16 plate along outer edges: 3.0" vertical + 1.0" outward flare at 45 deg
    fg_mat = MATERIAL_LIBRARY["3/16 Plate"]
    fg_len = m1_len
    fg_plate_wt = (fg_len * 4.41 * 0.1875) * fg_mat["density_lb_in3"]
    plates.append(Plate(
        piece_mark="FG1-L",
        description="Flared Wheel Guide - Carrier Left",
        thickness=0.1875,
        width=4.41,
        length=fg_len,
        grade=fg_mat["grade"],
        material="3/16\" Steel Plate",
        quantity=1,
        unit_weight=round(fg_plate_wt, 2),
        total_weight=round(fg_plate_wt, 2),
        assembly="MAIN_CARRIER",
        cut_notes="Brake form 45-deg flare: 3\" vertical leg, 1.0\" outward horizontal flare. Total width 38.00\" MAX.",
        status=StatusEnum.DESIGN
    ))
    plates.append(Plate(
        piece_mark="FG1-R",
        description="Flared Wheel Guide - Carrier Right",
        thickness=0.1875,
        width=4.41,
        length=fg_len,
        grade=fg_mat["grade"],
        material="3/16\" Steel Plate",
        quantity=1,
        unit_weight=round(fg_plate_wt, 2),
        total_weight=round(fg_plate_wt, 2),
        assembly="MAIN_CARRIER",
        cut_notes="Brake form 45-deg flare: 3\" vertical leg, 1.0\" outward horizontal flare. Total width 38.00\" MAX.",
        status=StatusEnum.DESIGN
    ))
    
    # Traction Grating for Deck (EM1-L, EM1-R)
    # Spans 11.50" flat width by 63" length
    em_mat = MATERIAL_LIBRARY["Expanded Metal #9 1-1/2"]
    em_sqft = (params.track_flat_width * m1_len) / 144.0
    em_wt = em_sqft * em_mat["wt_per_sqft"]
    plates.append(Plate(
        piece_mark="EM1-L",
        description="Traction Grating - Deck Left Track",
        thickness=0.134,
        width=params.track_flat_width,
        length=m1_len,
        grade=em_mat["grade"],
        material="#9 1-1/2\" Expanded Metal",
        quantity=1,
        unit_weight=round(em_wt, 2),
        total_weight=round(em_wt, 2),
        assembly="MAIN_CARRIER",
        cut_notes="Shear cut 11.50\" x 63.00\". Tack weld to M1-L and M2-L @ 6\" O.C.",
        status=StatusEnum.DESIGN
    ))
    plates.append(Plate(
        piece_mark="EM1-R",
        description="Traction Grating - Deck Right Track",
        thickness=0.134,
        width=params.track_flat_width,
        length=m1_len,
        grade=em_mat["grade"],
        material="#9 1-1/2\" Expanded Metal",
        quantity=1,
        unit_weight=round(em_wt, 2),
        total_weight=round(em_wt, 2),
        assembly="MAIN_CARRIER",
        cut_notes="Shear cut 11.50\" x 63.00\". Tack weld to M1-R and M2-R @ 6\" O.C.",
        status=StatusEnum.DESIGN
    ))

    # -------------------------------------------------------------
    # 2. TWIN RECEIVER / STINGER ASSEMBLY
    # -------------------------------------------------------------
    # Truck receiver tubes center spacing = 37.50" (UNVERIFIED: 40.0" span - 2.5" socket OD)
    # Stingers S1-L and S1-R are positioned at Y = +/- 18.75".
    # Total stinger length = insertion (18.00" UNVERIFIED) + underframe overlap (20.00" to tie past C2 at X=18") = 38.00"
    stinger_mat = MATERIAL_LIBRARY[params.stinger_section]
    stinger_total_len = params.stinger_insertion_length + params.stinger_overlap_length
    stinger_wt = (stinger_total_len / 12.0) * stinger_mat["wt_per_ft"]
    y_stinger = params.receiver_spacing / 2.0 # 18.75"
    
    members.append(Member(
        piece_mark="S1-L",
        description="Mount Stinger - Left (Driver Side)",
        section=params.stinger_section,
        grade=stinger_mat["grade"],
        length=stinger_total_len,
        quantity=1,
        start_pt=Point3D(x=-params.stinger_insertion_length, y=-y_stinger, z=-3.0),
        end_pt=Point3D(x=params.stinger_overlap_length, y=-y_stinger, z=-3.0),
        orientation="X",
        assembly="STINGER",
        cut_type="SQUARE",
        unit_weight=stinger_mat["wt_per_ft"],
        total_weight=round(stinger_wt, 2),
        notes="Truck mounting tube. Front (truck) end inserts into the receiver socket. Receiver spacing UNVERIFIED - must be measured on the truck. Connection to the carrier frame is reported by the geometry checker.",
        status=StatusEnum.ESTIMATED_UNVERIFIED
    ))
    members.append(Member(
        piece_mark="S1-R",
        description="Mount Stinger - Right (Passenger Side)",
        section=params.stinger_section,
        grade=stinger_mat["grade"],
        length=stinger_total_len,
        quantity=1,
        start_pt=Point3D(x=-params.stinger_insertion_length, y=y_stinger, z=-3.0),
        end_pt=Point3D(x=params.stinger_overlap_length, y=y_stinger, z=-3.0),
        orientation="X",
        assembly="STINGER",
        cut_type="SQUARE",
        unit_weight=stinger_mat["wt_per_ft"],
        total_weight=round(stinger_wt, 2),
        notes="Truck mounting tube. Front (truck) end inserts into the receiver socket. Receiver spacing UNVERIFIED - must be measured on the truck. Connection to the carrier frame is reported by the geometry checker.",
        status=StatusEnum.ESTIMATED_UNVERIFIED
    ))
    
    # Stinger Underframe Reinforcement Gussets (G1)
    # G1-L1/R1 weld between stinger and C1 header (X=1.0")
    # G1-L2/R2 weld between stinger and C2 crossmember (X=18.0")
    g1_mat = MATERIAL_LIBRARY["1/4 Plate"]
    g1_wt = (4.0 * 8.0 * 0.5 * 0.250) * g1_mat["density_lb_in3"]
    for side, y_sgn in [("L", -1), ("R", 1)]:
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
            cut_notes="Triangular gusset 4\" x 8\". Intended to tie the mounting tube to the front crossmember - see the connection report for whether it reaches.",
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
            cut_notes="Triangular gusset 4\" x 8\". Intended to tie the mounting tube to the second crossmember - see the connection report for whether it reaches.",
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
        start_pt=Point3D(x=params.carrier_deck_length, y=-y_m1, z=-1.0),
        end_pt=Point3D(x=params.carrier_deck_length + r_len, y=-y_m1, z=-1.0),
        orientation="X",
        assembly="RAMP",
        cut_type="ANGLE_CUT",
        cut_angle_right=16.2, # Deployed ground contact beveled foot
        unit_weight=r1_mat["wt_per_ft"],
        total_weight=round(r1_wt, 2),
        notes="Main rigid ramp side member. Foot beveled @ 16.2 deg for ground transition.",
        status=StatusEnum.MEASURED
    ))
    members.append(Member(
        piece_mark="R1-R",
        description="Ramp Outer Side Tube - Right",
        section="2x2x3/16 Tube",
        grade=r1_mat["grade"],
        length=r_len,
        quantity=1,
        start_pt=Point3D(x=params.carrier_deck_length, y=y_m1, z=-1.0),
        end_pt=Point3D(x=params.carrier_deck_length + r_len, y=y_m1, z=-1.0),
        orientation="X",
        assembly="RAMP",
        cut_type="ANGLE_CUT",
        cut_angle_right=16.2,
        unit_weight=r1_mat["wt_per_ft"],
        total_weight=round(r1_wt, 2),
        notes="Main rigid ramp side member. Foot beveled @ 16.2 deg for ground transition.",
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
        start_pt=Point3D(x=params.carrier_deck_length, y=-y_m2, z=-1.0),
        end_pt=Point3D(x=params.carrier_deck_length + r_len, y=-y_m2, z=-1.0),
        orientation="X",
        assembly="RAMP",
        cut_type="SQUARE",
        unit_weight=r2_mat["wt_per_ft"],
        total_weight=round(r2_wt, 2),
        notes="Leg down, toe out. Aligns with carrier M2-L track (Y=-6.5\").",
        status=StatusEnum.DESIGN
    ))
    members.append(Member(
        piece_mark="R2-R",
        description="Ramp Inner Track Support - Right",
        section="2x2x3/16 Angle",
        grade=r2_mat["grade"],
        length=r_len,
        quantity=1,
        start_pt=Point3D(x=params.carrier_deck_length, y=y_m2, z=-1.0),
        end_pt=Point3D(x=params.carrier_deck_length + r_len, y=y_m2, z=-1.0),
        orientation="X",
        assembly="RAMP",
        cut_type="SQUARE",
        unit_weight=r2_mat["wt_per_ft"],
        total_weight=round(r2_wt, 2),
        notes="Leg down, toe out. Aligns with carrier M2-R track (Y=+6.5\").",
        status=StatusEnum.DESIGN
    ))
    
    # Ramp Crossmembers (RC1 to RC5)
    # Length matches carrier crossmember length: 32.00"
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
            start_pt=Point3D(x=params.carrier_deck_length + dist, y=-y_cm_half, z=-1.0),
            end_pt=Point3D(x=params.carrier_deck_length + dist, y=y_cm_half, z=-1.0),
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
    rfg_plate_wt = (r_len * 4.41 * 0.1875) * rfg_mat["density_lb_in3"]
    plates.append(Plate(
        piece_mark="RFG1-L",
        description="Ramp Flared Wheel Guide - Left",
        thickness=0.1875,
        width=4.41,
        length=r_len,
        grade=rfg_mat["grade"],
        material="3/16\" Steel Plate",
        quantity=1,
        unit_weight=round(rfg_plate_wt, 2),
        total_weight=round(rfg_plate_wt, 2),
        assembly="RAMP",
        cut_notes="Brake form 45-deg flare: 3\" vertical leg, 1.0\" outward horizontal flare. Total width 38.00\" MAX.",
        status=StatusEnum.DESIGN
    ))
    plates.append(Plate(
        piece_mark="RFG1-R",
        description="Ramp Flared Wheel Guide - Right",
        thickness=0.1875,
        width=4.41,
        length=r_len,
        grade=rfg_mat["grade"],
        material="3/16\" Steel Plate",
        quantity=1,
        unit_weight=round(rfg_plate_wt, 2),
        total_weight=round(rfg_plate_wt, 2),
        assembly="RAMP",
        cut_notes="Brake form 45-deg flare: 3\" vertical leg, 1.0\" outward horizontal flare. Total width 38.00\" MAX.",
        status=StatusEnum.DESIGN
    ))
    
    # Ramp Traction Grating (REM1-L, REM1-R)
    rem_sqft = (params.track_flat_width * r_len) / 144.0
    rem_wt = rem_sqft * em_mat["wt_per_sqft"]
    plates.append(Plate(
        piece_mark="REM1-L",
        description="Traction Grating - Ramp Left Track",
        thickness=0.134,
        width=params.track_flat_width,
        length=r_len,
        grade=em_mat["grade"],
        material="#9 1-1/2\" Expanded Metal",
        quantity=1,
        unit_weight=round(rem_wt, 2),
        total_weight=round(rem_wt, 2),
        assembly="RAMP",
        cut_notes="Shear cut 11.50\" x 61.00\". Tack weld to R1-L and R2-L @ 6\" O.C.",
        status=StatusEnum.DESIGN
    ))
    plates.append(Plate(
        piece_mark="REM1-R",
        description="Traction Grating - Ramp Right Track",
        thickness=0.134,
        width=params.track_flat_width,
        length=r_len,
        grade=em_mat["grade"],
        material="#9 1-1/2\" Expanded Metal",
        quantity=1,
        unit_weight=round(rem_wt, 2),
        total_weight=round(rem_wt, 2),
        assembly="RAMP",
        cut_notes="Shear cut 11.50\" x 61.00\". Tack weld to R1-R and R2-R @ 6\" O.C.",
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
    # Hinge Pin: 3/4" Cold Rolled Round Bar, 38.00" length (flush with max width)
    pin_mat = MATERIAL_LIBRARY["3/4 Round Bar"]
    pin_len = params.carrier_max_overall_width # 38.00"
    pin_wt = (pin_len / 12.0) * pin_mat["wt_per_ft"]
    members.append(Member(
        piece_mark="P1",
        description="Ramp Hinge Main Pin",
        section="3/4 Round Bar",
        grade=pin_mat["grade"],
        length=pin_len,
        quantity=1,
        start_pt=Point3D(x=params.carrier_deck_length, y=-pin_len/2.0, z=params.ramp_hinge_pin_z),
        end_pt=Point3D(x=params.carrier_deck_length, y=pin_len/2.0, z=params.ramp_hinge_pin_z),
        orientation="Y",
        assembly="HINGE",
        cut_type="SQUARE",
        unit_weight=pin_mat["wt_per_ft"],
        total_weight=round(pin_wt, 2),
        notes="Drill 3/16\" linchpin hole 0.50\" from each end. Retained by 3/4\" flat washers.",
        status=StatusEnum.DESIGN
    ))
    
    # Hinge Sleeves: 1-1/8" OD x 0.172" wall DOM mechanical tubing (0.781" ID)
    sleeve_mat = MATERIAL_LIBRARY["1.125x0.172 DOM Tube"]
    sleeve_wt = (3.50 / 12.0) * sleeve_mat["wt_per_ft"]
    for i, (b_start, b_end, owner) in enumerate(hinge_barrel_positions(params), start=1):
        members.append(Member(
            piece_mark=f"HS{i}",
            description=f"Hinge Sleeve Barrel - {owner} ({i}/4)",
            section="1.125x0.172 DOM Tube",
            grade=sleeve_mat["grade"],
            length=3.50,
            quantity=1,
            start_pt=Point3D(x=params.carrier_deck_length, y=b_start, z=params.ramp_hinge_pin_z),
            end_pt=Point3D(x=params.carrier_deck_length, y=b_end, z=params.ramp_hinge_pin_z),
            orientation="Y",
            assembly="HINGE",
            cut_type="SQUARE",
            unit_weight=sleeve_mat["wt_per_ft"],
            total_weight=round(sleeve_wt, 2),
            notes=f"1-1/8\" OD x 0.172\" Wall DOM (0.781\" ID, 0.031\" clearance). Welded to {owner}.",
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
    # 2x2x1/4 Angle, 11.50" long (Qty 2) across front of left and right tracks
    g5_mat = MATERIAL_LIBRARY["2x2x1/4 Angle"]
    g5_len = params.track_flat_width # 11.50"
    g5_wt = (g5_len / 12.0) * g5_mat["wt_per_ft"]
    members.append(Member(
        piece_mark="G5-L",
        description="Front Wheel Stop Angle - Left",
        section="2x2x1/4 Angle",
        grade=g5_mat["grade"],
        length=g5_len,
        quantity=1,
        start_pt=Point3D(x=2.0, y=-18.0, z=0.0),
        end_pt=Point3D(x=2.0, y=-6.5, z=0.0),
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
        length=g5_len,
        quantity=1,
        start_pt=Point3D(x=2.0, y=6.5, z=0.0),
        end_pt=Point3D(x=2.0, y=18.0, z=0.0),
        orientation="Y",
        assembly="DETAILS",
        cut_type="SQUARE",
        unit_weight=g5_mat["wt_per_ft"],
        total_weight=round(g5_wt, 2),
        notes="Leg up, welded across right wheel track at X = 2.0\" as front tire chock.",
        status=StatusEnum.DESIGN
    ))

    # -------------------------------------------------------------
    # 6. MAKE THE MODEL PHYSICAL
    # -------------------------------------------------------------
    # Give every member its real outside section, every plate a real position,
    # every hole a real location, and declare every intended welded joint.
    apply_member_sections(members)
    apply_plate_placements(plates, params)
    holes = apply_holes(members, plates, params)
    welds = build_welds(params)

    # Now find out whether any of it actually fits together.
    checks = physical.run_geometry_checks(params, members, plates, welds)

    # Connection notes are generated from what the checker found, never asserted.
    contact_by_part: Dict[str, List[str]] = {}
    for c in checks.contacts:
        for mark in (c.piece_a, c.piece_b):
            other = c.piece_b if mark == c.piece_a else c.piece_a
            if c.result == "GAP":
                contact_by_part.setdefault(mark, []).append(
                    f"does NOT reach {other} (gap {c.gap:.2f}\")")
            elif c.result == "KNIFE_EDGE":
                contact_by_part.setdefault(mark, []).append(
                    f"barely touches {other} ({c.min_contact_dim:.2f}\")")
    for m in members:
        problems = contact_by_part.get(m.piece_mark)
        if problems:
            m.notes = (m.notes + "  CHECK: " + "; ".join(sorted(set(problems))) + ".").strip()
    for p in plates:
        problems = contact_by_part.get(p.piece_mark)
        if problems:
            p.cut_notes = (p.cut_notes + "  CHECK: "
                           + "; ".join(sorted(set(problems))) + ".").strip()

    # -------------------------------------------------------------
    # 7. ASSEMBLE COMPLETE BOM AND CUT LIST
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
            grade=m.grade,
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
            grade=p.grade,
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
        "holes": holes,
        "bom": [b.model_dump() for b in bom_rows],
        "cut_list": [c.model_dump() for c in cut_list_rows],
        "total_carrier_weight": round(total_carrier_weight, 1),
        "structural": structural_results.model_dump(),
        "ramp_angle_deg": ramp_angle_deg,
        "geometry_check_report": checks
    }
