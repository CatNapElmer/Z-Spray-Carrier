import math
from typing import List, Dict, Any, Tuple, Optional
from models import (
    ProjectParameters, StatusEnum, ParameterItem, Point3D, Hole, Weld,
    Member, Plate, HingeComponent, StructuralCheckResult, BomRow, CutListRow,
    BoxBounds, GeometryCheckReport
)
import physical

# The ramp's wheel guides stop this far back from the ramp's front end. That
# gap is the only reason the ramp can stand fully upright without its guides
# swinging into the deck guides. Do not close it up.
RAMP_GUIDE_SETBACK = 5.50

# Mounting-tube axis height below the deck running surface. The sleeved tube is
# 2-1/2 in deep, so its top face lands flush with the underside of the deck frame.
STINGER_AXIS_Z = -3.25

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
        "section_modulus": 0.872,
        "moment_of_inertia": 0.872,
        "category": "TUBE"
    },
    # Slip-over stinger reinforcement. 2.152" bore over a 2.000" tube, so it
    # slides on by hand. Used only OUTSIDE the truck socket.
    "2.5x2.5x3/16 Tube": {
        "type": "HSS",
        "name": "HSS 2-1/2x2-1/2x3/16",
        "width": 2.50,
        "height": 2.50,
        "thickness": 0.1875,
        "grade": "ASTM A500 Gr B",
        "wt_per_ft": 5.59,
        "area": 1.64,
        "section_modulus": 1.174,
        "moment_of_inertia": 1.468,
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
    # Hinge barrel stock - ordinary 1-1/4" OD x 3/16" wall DOM.
    # 7/8" bore over a 3/4" pin gives 1/8" of running clearance, which is loose
    # enough that weld distortion never needs reaming and tight enough not to
    # rattle. This is a stock size any supplier carries.
    "1.25x0.188 DOM Tube": {
        "type": "ROUND_TUBE",
        "name": "1-1/4\" OD x 3/16\" Wall DOM Hinge Barrel (7/8\" ID)",
        "od": 1.250,
        "id": 0.875,
        "wall": 0.1875,
        "grade": "ASTM A513 Type 5 DOM",
        "wt_per_ft": 2.13,
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
    Physical placement of every plate part, so plates take part in the envelope,
    contact and collision checks instead of floating free of the model.
    """
    y_out = params.carrier_width / 2.0                 # outer face of the side rails
    y_track_in = params.track_center_gap / 2.0         # inner track rail centreline
    guide_t = 0.1875
    guide_h = params.flared_guide_height
    flare = params.flare_width
    deck_l = params.carrier_deck_length
    hg = hinge_geometry(params)
    ramp_x0 = hg["ramp_front_x"]
    ramp_l = params.ramp_length

    place: Dict[str, Dict[str, Any]] = {}

    # --- Formed wheel guides. Folded shape, so an explicit envelope is used.
    #     The ramp guides stop short of the hinge; that gap is what lets the
    #     ramp stand up without its guides hitting the deck guides. ---
    guide_setback = RAMP_GUIDE_SETBACK
    for side, sgn in (("L", -1.0), ("R", 1.0)):
        for mark, x0, x1 in (("FG1-" + side, 0.0, deck_l),
                             ("RFG1-" + side, ramp_x0 + guide_setback,
                              ramp_x0 + ramp_l)):
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
        for mark, x0 in (("EM1-" + side, 0.0), ("REM1-" + side, ramp_x0)):
            place[mark] = {
                "origin": Point3D(x=x0, y=y_lo, z=0.0),
                "length_axis": "X", "width_axis": "Y", "normal_axis": "Z",
                "note": "Lies flat on top of the side rail and the inner track rail.",
            }

    # --- Ramp ground transition plate, lapped over the ramp tip. ---
    place["RF1"] = {
        "origin": Point3D(x=ramp_x0 + ramp_l - 3.0, y=-y_out, z=0.0),
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
            "note": ("Mounted on the outside face of the rear corner, hanging "
                     "below the deck. Exact position is a design choice."),
        }

    # --- Front chain / restraint bracket, standing up on the front cross tube. ---
    place["G4"] = {
        "origin": Point3D(x=1.00 - 0.375 / 2.0, y=-2.0, z=0.0),
        "length_axis": "Z", "width_axis": "Y", "normal_axis": "X",
        "note": ("Stands on edge in the middle of the front cross tube and is "
                 "welded all the way around its base."),
    }
    return place


def hinge_geometry(params: ProjectParameters) -> Dict[str, float]:
    """
    Every hinge coordinate, from one rule a fabricator can hold in his head:

        THE GAP BETWEEN THE DECK AND THE RAMP IS ONE BARREL DIAMETER.

    Lay a scrap of the barrel stock in the gap and that is the spacing. Each
    barrel then sits tangent in the corner of its own crossmember - bottom of
    the barrel flush with the top of the frame, back of the barrel against the
    crossmember face. Nothing here has to be measured to a thousandth.
    """
    od = params.hinge_barrel_od
    r = od / 2.0
    carrier_rear_x = params.carrier_deck_length      # back face of the deck frame
    return {
        "barrel_od": od,
        "barrel_radius": r,
        "carrier_rear_x": carrier_rear_x,
        "ramp_front_x": carrier_rear_x + od,         # gap = one barrel OD
        "gap": od,
        "pin_x": carrier_rear_x + r,
        "pin_z": r,                                  # deck top is Z = 0
    }


def hinge_barrel_positions(params: ProjectParameters
                           ) -> List[Tuple[float, float, str]]:
    """
    Barrel positions along the pin as (y_start, y_end, owner).

    Plain interleaved trailer hinge: barrels of equal length on equal centres,
    symmetric about the middle of the carrier, alternating carrier / ramp so the
    two halves comb together. The outermost barrels belong to the carrier.
    """
    n = int(params.hinge_barrel_count)
    length = params.hinge_barrel_length
    gap = params.hinge_barrel_gap
    pitch = length + gap
    span = n * length + (n - 1) * gap
    y0 = -span / 2.0
    out: List[Tuple[float, float, str]] = []
    for i in range(n):
        start = y0 + i * pitch
        out.append((round(start, 4), round(start + length, 4),
                    "Carrier" if i % 2 == 0 else "Ramp"))
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
    Attach every hole to the part it is drilled in, with a plain-English
    instruction. Holes that depend on the truck are marked field_fit so they are
    transferred from the truck, never drilled off a drawing dimension.
    """
    by_mark = {m.piece_mark: m for m in members}
    by_plate = {p.piece_mark: p for p in plates}
    all_holes: List[Hole] = []
    hg = hinge_geometry(params)

    def add_member_hole(mark: str, hole: Hole) -> None:
        m = by_mark.get(mark)
        if m is None:
            return
        hole.parent_mark = mark
        m.holes.append(hole)
        all_holes.append(hole)

    # --- Hitch pin holes through the two truck mounting tubes. ---
    y_stinger = params.stinger_spacing_model_nominal / 2.0
    for side, sgn in (("L", -1.0), ("R", 1.0)):
        add_member_hole(f"S1-{side}", Hole(
            hole_id=f"H-S1{side}-PIN",
            diameter=params.hitch_pin_hole_dia,
            center_x=-params.stinger_insertion_length + params.hitch_pin_hole_setback,
            center_y=sgn * y_stinger,
            center_z=STINGER_AXIS_Z,
            axis="Y",
            reference_edge="truck end of the mounting tube",
            offset_from_reference=params.hitch_pin_hole_setback,
            plain_instruction=(
                "TRANSFER PIN HOLES FROM TRUCK. Slide the tube into the socket, "
                "run the truck's own pin through, mark it, pull the tube and "
                "drill 21/32\" straight through both walls."),
            note="Do not drill from a drawing dimension.",
            field_fit=True,
            status=StatusEnum.FIELD_FIT,
        ))

    # --- Linchpin holes in the hinge pin. ---
    pin = by_mark.get("P1")
    if pin is not None:
        half = pin.length / 2.0
        for end, sgn in (("left", -1.0), ("right", 1.0)):
            add_member_hole("P1", Hole(
                hole_id=f"H-P1-{end.upper()}",
                diameter=0.1875,
                center_x=hg["pin_x"],
                center_y=sgn * (half - 0.50),
                center_z=hg["pin_z"],
                axis="Z",
                reference_edge=f"{end} end of the pin",
                offset_from_reference=0.50,
                plain_instruction=(
                    "Drill 3/16\" through the pin, 1/2\" in from the end, for "
                    "the hairpin clip. Flat washer under the clip."),
                status=StatusEnum.DESIGN,
            ))

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
        pl = by_plate.get(f"G2-{side}")
        if pl is None:
            continue
        h = Hole(
            hole_id=f"H-G2{side}", parent_mark=pl.piece_mark, diameter=2.50,
            center_x=params.carrier_deck_length - 4.0,
            center_y=sgn * (params.carrier_width / 2.0 + 0.09375),
            center_z=-3.0, axis="Y",
            reference_edge="rear edge of the guard plate",
            offset_from_reference=4.00,
            plain_instruction=("Cut the 6 3/4\" x 2 1/2\" oval for the light "
                               "grommet. Centre it 4\" from the rear edge and "
                               "halfway up the plate."),
            note="Oval cut-out, not a round hole.",
            status=StatusEnum.DESIGN,
        )
        pl.holes = [h]
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

    Declaring a weld here only claims these two pieces are meant to join. The
    geometry checker decides whether they actually touch.
    """
    w: List[Weld] = []
    cross = ["C1", "C2", "C3", "C4"]
    beams = ["MB1", "MB2", "MB3"]
    ramp_cross = ["RC1", "RC2", "RC3", "RC4", "RC5"]

    # --- Deck frame ---
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

    # --- Truck mounting: the under-deck beams are the load path. ---
    # Nothing here gets final-welded until the stingers are in the truck
    # sockets and the deck is clamped square behind the truck.
    for side in ("L", "R"):
        _weld(w, f"SL-{side}", f"S1-{side}", size="1/4", all_around=True,
              instruction="Weld the sleeve to the mounting tube all around at "
                          "both ends. Add one plug weld at each mount beam.",
              note="Sleeve slips on - it stops outside the truck socket.")
        for mb in beams:
            _weld(w, mb, f"SL-{side}", size="1/4", all_around=True,
                  field_fit=True,
                  instruction="TACK FIRST. Weld the mount beam to the sleeve "
                              "all around once the carrier is fitted to the truck.")
        _weld(w, f"SL-{side}", f"M1-{side}", weld_type="TACK", field_fit=True,
              instruction="Optional stitch along the seam where the sleeve runs "
                          "under the side rail - 2 in every 12 in. This is a "
                          "seal, not the load path.")
    for mb in beams:
        for rail in ("M1-L", "M1-R", "M2-L", "M2-R"):
            _weld(w, mb, rail, size="1/4", all_around=True, field_fit=True,
                  instruction="Weld the mount beam to the underside of the rail "
                              "all the way around where they cross.")
    # Each beam sits directly under a cross tube, making a closed box.
    for mb, cm in (("MB2", "C2"), ("MB3", "C3")):
        _weld(w, mb, cm, size="1/4", both_sides=True, field_fit=True,
              instruction="Weld both sides where the mount beam meets the "
                          "cross tube through the rails.")

    # --- Hinge: barrels sit in the corner of their own cross tube. ---
    for i, (_s, _e, owner) in enumerate(hinge_barrel_positions(params), start=1):
        host = "C4" if owner == "Carrier" else "RC1"
        _weld(w, f"HS{i}", host, size="1/4", both_sides=True,
              instruction="Barrel bottom flush with the top of the frame, back "
                          "of the barrel against the cross tube face. Fillet "
                          "above and below, full length of the barrel.")

    # --- Ramp ---
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


def fabrication_sequence() -> List[str]:
    """Plain shop build order. This is the order the thing actually goes together."""
    return [
        "Build the deck frame flat on horses and square it - two side rails, two "
        "inner track rails, four cross tubes. Check the diagonals.",
        "Build the ramp frame the same way - two side rails, two inner rails, "
        "five cross pieces. Check the diagonals.",
        "Set the deck and the ramp on the floor nose to nose. Set the gap with a "
        "scrap of the barrel stock laid in it - the gap IS one barrel diameter.",
        "Slide all seven barrels onto the pin. Drop the pin assembly into the "
        "corner: barrel bottoms flush with the top of the frames, barrel backs "
        "against the cross tube faces. Clamp. TACK ONLY.",
        "CHECK RAMP SWING BEFORE FINAL WELD. Swing the ramp by hand from flat "
        "to straight up. If it rubs, ease the leading edge of the cross tube "
        "with a grinder. Then finish weld the barrels.",
        "Slide both mounting tubes into the truck sockets and pin them. "
        "TRANSFER PIN HOLES FROM TRUCK if the tubes are not drilled yet.",
        "Roll the deck up behind the truck, set it level and square, and clamp "
        "it to the mounting tubes. FIELD FIT TO TRUCK - do not measure this.",
        "Cut the three under-deck mount beams to fit between the two mounting "
        "tubes. Clamp and tack them to the tubes and up to the rails.",
        "Slip the two reinforcing sleeves on over the mounting tubes, up against "
        "the socket faces. Tack.",
        "Pull the pins and take the carrier off the truck.",
        "Finish weld everything on the ground where you can get at it.",
        "Fit the wheel tracks, the expanded metal and the flared guides.",
        "Hang the carrier back on the truck and roll the Z-Spray on.",
        "CHECK MACHINE CLEARANCE DURING FIT-UP. Pull the machine forward, then "
        "set the upright ramp about 1\" behind the rear tires and mark it.",
        "Fit the lights, wiring, chain bracket and remaining hardware.",
    ]


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
        "stinger_spacing_model_nominal": ParameterItem(
            name="stinger_spacing_model_nominal",
            value=params.stinger_spacing_model_nominal,
            units="in",
            status=StatusEnum.MODEL_ONLY,
            description="Drawing coordinate only - NOT a shop dimension",
            source_note="FIELD FIT TO TRUCK. The program needs a number to draw "
                        "the two mounting tubes. On the shop floor you slide "
                        "them into the truck's own sockets - the truck sets the "
                        "spacing. Never measure or lay out from this value.",
            required_before_fabrication=False
        ),
        "stinger_overlap_length": ParameterItem(
            name="stinger_overlap_length",
            value=params.stinger_overlap_length,
            units="in",
            status=StatusEnum.DESIGN,
            description="How far the mounting tubes run back under the deck",
            source_note="Runs back past all three under-deck mount beams so the "
                        "load spreads over a long base instead of one point.",
            required_before_fabrication=False
        ),
        "stinger_sleeve_length": ParameterItem(
            name="stinger_sleeve_length",
            value=params.stinger_sleeve_length,
            units="in",
            status=StatusEnum.DESIGN,
            description="Slip-over reinforcing sleeve length",
            source_note="Slides on from outside the truck socket. Nothing that "
                        "goes inside the socket is changed.",
            required_before_fabrication=False
        ),
        "stinger_insertion_length": ParameterItem(
            name="stinger_insertion_length",
            value=params.stinger_insertion_length,
            units="in",
            status=StatusEnum.FIELD_FIT,
            description="Nominal depth into the truck socket",
            source_note="FIELD FIT TO TRUCK. Push the tube in until it stops.",
            required_before_fabrication=False
        ),
        "hitch_pin_hole_setback": ParameterItem(
            name="hitch_pin_hole_setback",
            value=params.hitch_pin_hole_setback,
            units="in",
            status=StatusEnum.FIELD_FIT,
            description="Nominal hitch pin hole position",
            source_note="TRANSFER PIN HOLES FROM TRUCK. Slide the tube in, run "
                        "the truck's pin through, mark it, then drill.",
            required_before_fabrication=False
        ),
        "ramp_clearance": ParameterItem(
            name="ramp_clearance",
            value=params.ramp_clearance,
            units="in",
            status=StatusEnum.FIELD_FIT,
            description="Gap behind the rear tires with the ramp upright",
            source_note="CHECK DURING MACHINE FIT-UP. Roll the machine on, pull "
                        "it forward, then set the ramp about 1 in behind the "
                        "rear tires and mark it.",
            required_before_fabrication=False
        ),
        "hinge_barrel_od": ParameterItem(
            name="hinge_barrel_od",
            value=params.hinge_barrel_od,
            units="in",
            status=StatusEnum.DESIGN,
            description="Hinge barrel outside diameter - also the deck-to-ramp gap",
            source_note="1-1/4 in OD x 3/16 in wall DOM, 7/8 in bore over a 3/4 in "
                        "pin. The gap between the deck and the ramp is exactly "
                        "one barrel diameter - lay a scrap of the barrel stock "
                        "in the gap to set it.",
            required_before_fabrication=False
        ),
        "hinge_pin_dia": ParameterItem(
            name="hinge_pin_dia",
            value=params.hinge_pin_dia,
            units="in",
            status=StatusEnum.DESIGN,
            description="Ramp hinge pin diameter",
            source_note="3/4 in cold-finished round bar, one continuous piece "
                        "through every barrel.",
            required_before_fabrication=False
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
        "hinge_barrel_id": ParameterItem(
            name="hinge_barrel_id",
            value=params.hinge_barrel_id,
            units="in",
            status=StatusEnum.DESIGN,
            description="Hinge barrel bore",
            source_note="7/8 in bore on a 3/4 in pin leaves 1/8 in of slop. That "
                        "is on purpose: it swings freely and never needs "
                        "reaming after welding.",
            required_before_fabrication=False
        ),
        "deck_height": ParameterItem(
            name="deck_height",
            value=params.deck_height,
            units="in",
            status=StatusEnum.DESIGN,
            description="Deck running surface height above ground",
            source_note="About 17 in. Set by the truck socket height plus the "
                        "depth of the sleeved mounting tube and the frame.",
            required_before_fabrication=False
        ),
    }

def _section_props(section: str) -> Tuple[float, float, float]:
    """(area, section modulus, moment of inertia) for a stock section."""
    mat = MATERIAL_LIBRARY.get(section, {})
    s = float(mat.get("section_modulus", 0.7))
    i = float(mat.get("moment_of_inertia", s))
    a = float(mat.get("area", 1.4))
    return a, s, i


def calculate_structural_checks(params: ProjectParameters,
                                carrier_dead_weight: float,
                                ramp_weight: float = 0.0) -> StructuralCheckResult:
    """
    Plain sanity check on the carrier, not an engineering report.

    The whole carrier hangs off two mounting tubes in the truck's two sockets.
    By statics the bending at the socket mouth is just (weight x how far back it
    sits), split between two tubes - it does not matter how the load gets there.
    So that is what we check, plus a hard stop and a hard corner.

    Acceptance rule: nothing yields at the bump factor (2.0 g). That is the same
    as a factor of 2 against yield on the static load. We do NOT stack another
    safety factor on top of an already-factored load - that would be a 4 g bar
    and would make this carrier absurdly heavy for no reason.
    """
    fy = params.material_yield_strength
    chem_wt = params.spray_tank_gallons * params.liquid_density_lb_gal
    fert_wt = params.fertilizer_hopper_weight + params.fertilizer_trays_weight
    payload_wt = params.machine_curb_weight + chem_wt + fert_wt
    total_suspended = payload_wt + carrier_dead_weight

    # --- Where the weight sits, measured back from the truck. ---
    cg_x = params.machine_cg_from_deck_front
    deck_wt = max(0.0, carrier_dead_weight - ramp_weight)
    ramp_arm = params.carrier_deck_length + 1.0     # stowed upright at the back
    moment_total = payload_wt * cg_x + deck_wt * cg_x + ramp_weight * ramp_arm
    moment_per_tube = moment_total / 2.0

    # --- The mounting tube is a 2x2 with a 2-1/2 sleeve slid over it, outside
    #     the socket. Two nested tubes bend together, so they split the moment
    #     by stiffness. No shear studs, no composite action needed. ---
    a_t, s_t, i_t = _section_props(params.stinger_section)
    a_s, s_s, i_s = _section_props(params.stinger_sleeve_section)
    i_tot = i_t + i_s
    area_tot = a_t + a_s
    stress_tube = moment_per_tube * (i_t / i_tot) / s_t if s_t else 0.0
    stress_sleeve = moment_per_tube * (i_s / i_tot) / s_s if s_s else 0.0
    vert_stress = max(stress_tube, stress_sleeve)
    yields_at_g = fy / vert_stress if vert_stress > 0 else 999.0
    vert_ok = yields_at_g >= params.vertical_dynamic_factor

    # Bare tube with no sleeve, so the report can show why the sleeve is there.
    bare_stress = moment_per_tube / s_t if s_t else 0.0
    bare_yields_at_g = fy / bare_stress if bare_stress > 0 else 999.0

    # --- Hard stop: 1 g down plus 0.8 g forward, machine CG about 21 in above
    #     the mounting tubes. Both act in the same plane, so they add. ---
    cg_z = 21.0
    brake_moment = (total_suspended * params.braking_factor * cg_z) / 2.0
    brake_total_moment = moment_per_tube + brake_moment
    brake_stress = brake_total_moment * (i_s / i_tot) / s_s if s_s else 0.0
    brake_stress = max(brake_stress,
                       brake_total_moment * (i_t / i_tot) / s_t if s_t else 0.0)
    brake_fos = fy / brake_stress if brake_stress > 0 else 999.0

    # --- Hard corner: the side load is carried as a push/pull couple between
    #     the two tubes. Use a deliberately SHORT tube spacing so the couple is
    #     over-estimated rather than under-estimated - the real spacing is set
    #     by the truck and is wider than this. ---
    conservative_spacing = 30.0
    lat_force = total_suspended * params.lateral_factor
    couple_axial = lat_force * cg_z / conservative_spacing
    lat_axial_stress = couple_axial / area_tot if area_tot else 0.0
    # Sideways bending only reaches from the socket mouth to the first mount
    # beam. Beyond that the beams hold the tube straight.
    lat_arm = params.mount_beam_stations[0] if params.mount_beam_stations else 4.0
    lat_bend_stress = ((lat_force / 2.0) * lat_arm) / (s_t + s_s) if (s_t + s_s) else 0.0
    lat_stress = vert_stress + lat_axial_stress + lat_bend_stress
    lat_fos = fy / lat_stress if lat_stress > 0 else 999.0

    cases = [("VERTICAL", yields_at_g, params.vertical_dynamic_factor, vert_stress),
             ("BRAKING", brake_fos, 1.5, brake_stress),
             ("LATERAL", lat_fos, 1.5, lat_stress)]
    controlling_case, controlling_margin, _req, controlling_stress = min(
        cases, key=lambda c: c[1] / c[2])
    is_adequate = all(fos >= req for _n, fos, req, _s in cases)

    load_cases = {
        "VERTICAL": {
            "description": f"Rough road bump. Nothing may yield at "
                           f"{params.vertical_dynamic_factor:.1f} g.",
            "load_lb": round(total_suspended, 1),
            "moment_in_lb": round(moment_total, 0),
            "per_stinger_moment_in_lb": round(moment_per_tube, 0),
            "stinger_stress_psi": round(vert_stress, 0),
            "yields_at_g": round(yields_at_g, 2),
            "factor_of_safety": round(yields_at_g, 2),
            "target_fos": params.vertical_dynamic_factor,
            "status": "PASS" if vert_ok else "FAIL",
        },
        "BRAKING": {
            "description": "Hard stop: 1.0 g down plus 0.8 g forward.",
            "load_lb": round(total_suspended * params.braking_factor, 1),
            "moment_in_lb": round(brake_total_moment * 2.0, 0),
            "per_stinger_moment_in_lb": round(brake_total_moment, 0),
            "stinger_stress_psi": round(brake_stress, 0),
            "factor_of_safety": round(brake_fos, 2),
            "target_fos": 1.5,
            "status": "PASS" if brake_fos >= 1.5 else "FAIL",
        },
        "LATERAL": {
            "description": "Hard corner: 1.0 g down plus 0.5 g sideways.",
            "load_lb": round(lat_force, 1),
            "moment_in_lb": round(lat_force * cg_z, 0),
            "per_stinger_moment_in_lb": round(moment_per_tube, 0),
            "stinger_stress_psi": round(lat_stress, 0),
            "factor_of_safety": round(lat_fos, 2),
            "target_fos": 1.5,
            "status": "PASS" if lat_fos >= 1.5 else "FAIL",
        },
        "CONTROLLING": {
            "governing_case": controlling_case,
            "controlling_stress_psi": round(controlling_stress, 0),
            "factor_of_safety": round(controlling_margin, 2),
            "target_fos": params.target_safety_factor,
            "status": "PASS" if is_adequate else "FAIL",
        },
    }

    # -------------------------------------------------------------
    # Hinge. Worst realistic case is the machine's back axle sitting right on
    # the hinge line while it drives on, plus a bounce.
    # -------------------------------------------------------------
    hinge_load = payload_wt * 0.75 * 1.5 + ramp_weight * 0.5
    n_barrels = max(2, int(params.hinge_barrel_count))
    shear_planes = n_barrels - 1
    pin_area = math.pi * (params.hinge_pin_dia ** 2) / 4.0
    pin_shear = (hinge_load / shear_planes) / pin_area if pin_area else 0.0
    pin_shear_allow = 0.4 * 54000.0
    load_per_barrel = hinge_load / n_barrels
    bearing = load_per_barrel / (params.hinge_pin_dia * params.hinge_barrel_length)
    # Rear cross tube spanning between the side rails, carrying its barrels.
    _a4, s_c4, _i4 = _section_props("2x2x1/4 Tube")
    span = params.carrier_width - 4.0
    c4_moment = (hinge_load / 2.0) * (span / 2.0) - load_per_barrel * (span / 4.0)
    c4_stress = abs(c4_moment) / s_c4 if s_c4 else 0.0
    # Two fillets the full length of each barrel.
    weld_capacity = (2.0 * params.hinge_barrel_length) * 0.133 * 21000.0

    hinge_check = {
        "pin_diameter_in": params.hinge_pin_dia,
        "barrel_od_in": params.hinge_barrel_od,
        "barrel_id_in": params.hinge_barrel_id,
        "barrel_count": n_barrels,
        "shear_planes": shear_planes,
        "diametral_clearance_in": round(params.hinge_barrel_id - params.hinge_pin_dia, 4),
        "clearance_status": "PASS" if 0.030 <= (params.hinge_barrel_id
                                                - params.hinge_pin_dia) <= 0.200 else "FAIL",
        "design_load_lb": round(hinge_load, 0),
        "pin_shear_stress_psi": round(pin_shear, 0),
        "pin_shear_fos": round(pin_shear_allow / pin_shear, 1) if pin_shear > 0 else 999.0,
        "pin_shear_status": "PASS" if pin_shear < pin_shear_allow else "FAIL",
        "barrel_bearing_stress_psi": round(bearing, 0),
        "cross_tube_stress_psi": round(c4_stress, 0),
        "cross_tube_status": "PASS" if c4_stress < fy else "FAIL",
        "weld_capacity_lb_per_barrel": round(weld_capacity, 0),
        "weld_demand_lb_per_barrel": round(load_per_barrel, 0),
        "weld_status": "PASS" if load_per_barrel < weld_capacity else "FAIL",
    }

    recommendations: List[str] = []
    if bare_yields_at_g < params.vertical_dynamic_factor:
        recommendations.append(
            f"The bare {params.stinger_section} mounting tube on its own would "
            f"yield at about {bare_yields_at_g:.1f} g, which is not enough. That "
            f"is why the {params.stinger_sleeve_section} sleeve slides over it "
            f"outside the socket. Do not leave the sleeves off.")
    if not vert_ok:
        recommendations.append(
            "Mounting tube bending is still too high. Go up a sleeve wall "
            "thickness, or shorten the deck. Do NOT brace to the truck.")
    if not is_adequate:
        recommendations.append(
            "Review the failing load case above before hauling a loaded machine.")

    notes = [
        f"Weight on the truck: machine and load {payload_wt:.0f} lb plus carrier "
        f"{carrier_dead_weight:.0f} lb = {total_suspended:.0f} lb total.",
        f"Bending at the socket, per mounting tube: {moment_per_tube:.0f} in-lb "
        f"with the load about {cg_x:.0f} in back from the truck.",
        f"Mounting tube with its sleeve: {vert_stress:.0f} psi against "
        f"{fy:.0f} psi yield - nothing yields until about {yields_at_g:.1f} g.",
        f"Bare tube without the sleeve would yield at about "
        f"{bare_yields_at_g:.1f} g. The sleeve is doing real work.",
        f"Hard stop factor {brake_fos:.1f}; hard corner factor {lat_fos:.1f}.",
        f"Hinge at {hinge_load:.0f} lb: pin {pin_shear:.0f} psi shear over "
        f"{shear_planes} shear planes, cross tube {c4_stress:.0f} psi. "
        f"Barrel welds carry {weld_capacity:.0f} lb each against "
        f"{load_per_barrel:.0f} lb.",
    ]

    return StructuralCheckResult(
        payload_weight=round(payload_wt, 1),
        carrier_dead_weight=round(carrier_dead_weight, 1),
        total_suspended_weight=round(total_suspended, 1),
        dynamic_vertical_load=round(total_suspended * params.vertical_dynamic_factor, 1),
        dynamic_moment_in_lb=round(moment_total, 0),
        stinger_reaction_force_lb=round(total_suspended / 2.0, 1),
        stinger_bending_stress_psi=round(vert_stress, 0),
        yield_strength_psi=fy,
        factor_of_safety=round(yields_at_g, 2),
        yields_at_g=round(yields_at_g, 2),
        target_safety_factor=params.target_safety_factor,
        controlling_load_case=controlling_case,
        controlling_stress_psi=round(controlling_stress, 0),
        is_adequate=is_adequate,
        status="PASS" if is_adequate else "FAIL",
        load_cases=load_cases,
        hinge_check=hinge_check,
        reinforcement_recommendations=recommendations,
        notes=notes,
    )


def generate_fabrication_assembly(params: ProjectParameters) -> Dict[str, Any]:
    """
    Builds the whole carrier as real pieces of steel in real positions.

    Coordinates:
      X = 0 at the front (truck) face of the deck frame, positive rearward
      Y = 0 on the carrier centreline
      Z = 0 at the deck running surface
    """
    members: List[Member] = []
    plates: List[Plate] = []

    hg = hinge_geometry(params)
    deck_l = params.carrier_deck_length
    ramp_x0 = hg["ramp_front_x"]
    r_len = params.ramp_length
    y_m1 = params.carrier_width / 2.0 - 1.0        # 17.00" side rail centreline
    y_m2 = params.track_center_gap / 2.0           # 6.50" inner rail centreline
    cm_len = params.carrier_width - 4.00           # 32.00" between the side rails
    y_cm = cm_len / 2.0

    def add_member(mark, desc, section, length, p0, p1, orient, assembly,
                   notes="", status=StatusEnum.DESIGN, cut_type="SQUARE",
                   cut_angle_right=0.0, field_fit=False, nested_over=""):
        mat = MATERIAL_LIBRARY[section]
        wt = (length / 12.0) * mat["wt_per_ft"]
        members.append(Member(
            piece_mark=mark, description=desc, section=section,
            grade=mat["grade"], length=round(length, 3), quantity=1,
            start_pt=p0, end_pt=p1, orientation=orient, assembly=assembly,
            cut_type=cut_type, cut_angle_right=cut_angle_right,
            unit_weight=mat["wt_per_ft"], total_weight=round(wt, 2),
            notes=notes, field_fit=field_fit, nested_over=nested_over,
            status=status))

    # -------------------------------------------------------------
    # 1. DECK FRAME
    # -------------------------------------------------------------
    for side, sgn in (("L", -1.0), ("R", 1.0)):
        who = "Left / Driver" if side == "L" else "Right / Passenger"
        add_member(f"M1-{side}", f"Deck Side Rail - {who}", "2x2x3/16 Tube",
                   deck_l, Point3D(x=0.0, y=sgn * y_m1, z=-1.0),
                   Point3D(x=deck_l, y=sgn * y_m1, z=-1.0), "X", "MAIN_CARRIER",
                   notes="Full length deck side tube. Outside faces set the "
                         "36 in frame width.")
        add_member(f"M2-{side}", f"Deck Inner Track Rail - {who}",
                   "2x2x3/16 Angle", deck_l,
                   Point3D(x=0.0, y=sgn * y_m2, z=-1.0),
                   Point3D(x=deck_l, y=sgn * y_m2, z=-1.0), "X", "MAIN_CARRIER",
                   notes="Leg down, toe out. Carries the inside edge of the "
                         "wheel track.")

    for mark, x_loc, section, desc in (
            ("C1", 1.00, "2x2x3/16 Tube", "Front Cross Tube (truck side)"),
            ("C2", 18.00, "2x2x3/16 Tube", "Cross Tube - over mount beam MB2"),
            ("C3", 38.00, "2x2x3/16 Tube", "Cross Tube - over mount beam MB3"),
            ("C4", 62.00, "2x2x1/4 Tube", "Rear Hinge Cross Tube (ramp side)")):
        add_member(mark, desc, section, cm_len,
                   Point3D(x=x_loc, y=-y_cm, z=-1.0),
                   Point3D(x=x_loc, y=y_cm, z=-1.0), "Y", "MAIN_CARRIER",
                   notes=f"Cross tube. Centre {x_loc:.0f} in back from the truck "
                         f"end of the side rails.")

    # -------------------------------------------------------------
    # 2. TRUCK MOUNT: two stingers + three under-deck mount beams
    # -------------------------------------------------------------
    # The two mounting tubes are located by the truck itself. The three
    # transverse beams underneath tie them into the deck frame with broad flat
    # welds - that is the load path, not the corner of a rail.
    y_sting = params.stinger_spacing_model_nominal / 2.0
    sl_w, _sl_d = section_outside_dims(params.stinger_sleeve_section)
    st_total = params.stinger_insertion_length + params.stinger_overlap_length
    for side, sgn in (("L", -1.0), ("R", 1.0)):
        who = "Left / Driver" if side == "L" else "Right / Passenger"
        add_member(
            f"S1-{side}", f"Truck Mounting Tube - {who}", params.stinger_section,
            st_total,
            Point3D(x=-params.stinger_insertion_length, y=sgn * y_sting, z=STINGER_AXIS_Z),
            Point3D(x=params.stinger_overlap_length, y=sgn * y_sting, z=STINGER_AXIS_Z),
            "X", "STINGER", status=StatusEnum.FIELD_FIT, field_fit=True,
            notes="FIELD FIT TO TRUCK. Cut long, slide into the truck socket, "
                  "trim the back end after the deck is clamped in place. "
                  "The truck sets the spacing - it is not a drawing dimension.")
        add_member(
            f"SL-{side}", f"Mounting Tube Sleeve - {who}",
            params.stinger_sleeve_section, params.stinger_sleeve_length,
            Point3D(x=0.5, y=sgn * y_sting, z=STINGER_AXIS_Z),
            Point3D(x=0.5 + params.stinger_sleeve_length, y=sgn * y_sting, z=STINGER_AXIS_Z),
            "X", "STINGER", status=StatusEnum.FIELD_FIT, field_fit=True,
            nested_over=f"S1-{side}",
            notes="Slips over the mounting tube. Slide it up against the truck "
                  "socket face and weld. Nothing inside the socket is changed.")

    mb_len = 2.0 * (y_sting - sl_w / 2.0)
    for i, x0 in enumerate(params.mount_beam_stations, start=1):
        add_member(
            f"MB{i}", f"Under-Deck Mount Beam {i} of 3", params.mount_beam_section,
            mb_len, Point3D(x=x0 + 1.0, y=-mb_len / 2.0, z=STINGER_AXIS_Z + 0.25),
            Point3D(x=x0 + 1.0, y=mb_len / 2.0, z=STINGER_AXIS_Z + 0.25),
            "Y", "STINGER", status=StatusEnum.FIELD_FIT, field_fit=True,
            notes=f"CUT TO FIT between the two mounting tubes - approx "
                  f"{mb_len:.0f} in. Sits flat under the deck rails and butts "
                  f"the sleeves. Weld all round.")

    # -------------------------------------------------------------
    # 3. RAMP FRAME (one rigid assembly)
    # -------------------------------------------------------------
    for side, sgn in (("L", -1.0), ("R", 1.0)):
        who = "Left / Driver" if side == "L" else "Right / Passenger"
        add_member(f"R1-{side}", f"Ramp Side Rail - {who}", "2x2x3/16 Tube",
                   r_len, Point3D(x=ramp_x0, y=sgn * y_m1, z=-1.0),
                   Point3D(x=ramp_x0 + r_len, y=sgn * y_m1, z=-1.0), "X", "RAMP",
                   cut_type="ANGLE_CUT", cut_angle_right=16.0,
                   notes="Ramp side tube. Bevel the ground end so the tire rolls "
                         "on smoothly.")
        add_member(f"R2-{side}", f"Ramp Inner Track Rail - {who}",
                   "2x2x3/16 Angle", r_len,
                   Point3D(x=ramp_x0, y=sgn * y_m2, z=-1.0),
                   Point3D(x=ramp_x0 + r_len, y=sgn * y_m2, z=-1.0), "X", "RAMP",
                   notes="Leg down, toe out. Lines up with the deck track rail.")

    add_member("RC1", "Ramp Head Cross Tube (carries hinge barrels)",
               "2x2x1/4 Tube", cm_len,
               Point3D(x=ramp_x0 + 1.0, y=-y_cm, z=-1.0),
               Point3D(x=ramp_x0 + 1.0, y=y_cm, z=-1.0), "Y", "RAMP",
               notes="Front cross tube of the ramp. Its top face and front face "
                     "form the corner the ramp barrels sit in.")
    for mark, dist in (("RC2", 15.0), ("RC3", 30.0), ("RC4", 45.0), ("RC5", 60.0)):
        add_member(mark, f"Ramp Cross Piece at {dist:.0f} in", "2x2x3/16 Angle",
                   cm_len, Point3D(x=ramp_x0 + dist, y=-y_cm, z=-1.0),
                   Point3D(x=ramp_x0 + dist, y=y_cm, z=-1.0), "Y", "RAMP",
                   notes=f"{dist:.0f} in back from the front end of the ramp rails.")

    # -------------------------------------------------------------
    # 4. HINGE - one pin, interleaved barrels, no ears, no machining
    # -------------------------------------------------------------
    add_member("P1", "Ramp Hinge Pin", "3/4 Round Bar", params.hinge_pin_length,
               Point3D(x=hg["pin_x"], y=-params.hinge_pin_length / 2.0, z=hg["pin_z"]),
               Point3D(x=hg["pin_x"], y=params.hinge_pin_length / 2.0, z=hg["pin_z"]),
               "Y", "HINGE",
               notes="One continuous pin through all barrels. Drill 3/16 in for a "
                     "hairpin clip 1/2 in from each end, washer under the clip.")
    for i, (b0, b1, owner) in enumerate(hinge_barrel_positions(params), start=1):
        host = "C4" if owner == "Carrier" else "RC1"
        add_member(
            f"HS{i}", f"Hinge Barrel {i} of {params.hinge_barrel_count} - "
                     f"{'carrier side' if owner == 'Carrier' else 'ramp side'}",
            "1.25x0.188 DOM Tube", params.hinge_barrel_length,
            Point3D(x=hg["pin_x"], y=b0, z=hg["pin_z"]),
            Point3D(x=hg["pin_x"], y=b1, z=hg["pin_z"]), "Y", "HINGE",
            notes=f"Welds to {host}. 1-1/4 in OD x 3/16 in wall, 7/8 in bore - "
                  f"1/8 in loose on the pin so it never needs reaming.")

    # -------------------------------------------------------------
    # 5. WHEEL TRACKS, GUIDES AND DETAILS
    # -------------------------------------------------------------
    guide_dev = params.flared_guide_height + params.flare_width * 1.414
    rfg_len = r_len - RAMP_GUIDE_SETBACK

    def add_plate(mark, desc, thk, width, length, material_key, assembly,
                  cut_notes, holes=None, profile=None):
        mat = MATERIAL_LIBRARY[material_key]
        if mat.get("category") == "GRATING":
            wt = (width * length / 144.0) * mat["wt_per_sqft"]
        else:
            wt = width * length * thk * mat["density_lb_in3"]
        plates.append(Plate(
            piece_mark=mark, description=desc, thickness=thk,
            width=round(width, 3), length=round(length, 3),
            profile_pts=profile or [], holes=holes or [],
            grade=mat["grade"], material=mat["name"], quantity=1,
            unit_weight=round(wt, 2), total_weight=round(wt, 2),
            assembly=assembly, cut_notes=cut_notes, status=StatusEnum.DESIGN))

    for side in ("L", "R"):
        who = "Left / Driver" if side == "L" else "Right / Passenger"
        add_plate(f"FG1-{side}", f"Deck Flared Wheel Guide - {who}", 0.1875,
                  guide_dev, deck_l, "3/16 Plate", "MAIN_CARRIER",
                  "Brake form: 3 in up, then 1 in out at 45 deg. Runs the full "
                  "length of the deck.")
        add_plate(f"RFG1-{side}", f"Ramp Flared Wheel Guide - {who}", 0.1875,
                  guide_dev, rfg_len, "3/16 Plate", "RAMP",
                  f"Brake form the same as the deck guide. STARTS "
                  f"{RAMP_GUIDE_SETBACK:.2f} IN BACK FROM THE FRONT END OF THE "
                  f"RAMP - that gap is what lets the ramp stand up. Do not run "
                  f"it to the hinge.")
        add_plate(f"EM1-{side}", f"Deck Traction Grating - {who}", 0.134,
                  params.track_flat_width, deck_l,
                  "Expanded Metal #9 1-1/2", "MAIN_CARRIER",
                  f"Shear {params.track_flat_width:.2f} x {deck_l:.0f} in. Tack "
                  f"down every 6 in.")
        add_plate(f"REM1-{side}", f"Ramp Traction Grating - {who}", 0.134,
                  params.track_flat_width, r_len,
                  "Expanded Metal #9 1-1/2", "RAMP",
                  f"Shear {params.track_flat_width:.2f} x {r_len:.0f} in. Tack "
                  f"down every 6 in.")
        add_plate(f"G2-{side}", f"Rear Light Guard Box - {who}", 0.1875, 6.0, 8.0,
                  "3/16 Plate", "DETAILS",
                  "Formed corner box. Steel stands 1-1/2 in proud of the lens.",
                  holes=[Hole(diameter=2.50, center_x=4.0, center_y=3.0,
                              center_z=0.0, reference_datum="PLATE_EDGE",
                              note="6 3/4 x 2 1/2 in oval cutout for a 6 in LED "
                                   "stop/turn/tail lamp")],
                  profile=[(0, 0), (8, 0), (8, 6), (0, 6)])

    add_plate("RF1", "Ramp Ground Transition Plate", 0.250, 3.0,
              params.carrier_width, "1/4 Plate", "RAMP",
              "Lapped over the ramp tip. Bevel the ground edge about 15 deg.")
    add_plate("G4", "Front Chain Tie-Down Bracket", 0.375, 4.0, 5.0,
              "3/8 Plate", "DETAILS",
              "Knock the corners off. Weld all round to the front cross tube.")

    for side, sgn in (("L", -1.0), ("R", 1.0)):
        who = "Left / Driver" if side == "L" else "Right / Passenger"
        y_a, y_b = sorted([sgn * (params.carrier_width / 2.0), sgn * y_m2])
        add_member(f"G5-{side}", f"Front Wheel Stop - {who}", "2x2x1/4 Angle",
                   params.track_flat_width, Point3D(x=4.5, y=y_a, z=1.0),
                   Point3D(x=4.5, y=y_b, z=1.0), "Y", "DETAILS",
                   notes="Leg up. Sits on top of the deck as a front tire chock.")

    # -------------------------------------------------------------
    # 6. MAKE THE MODEL PHYSICAL AND CHECK IT
    # -------------------------------------------------------------
    apply_member_sections(members)
    apply_plate_placements(plates, params)
    holes = apply_holes(members, plates, params)
    welds = build_welds(params)
    checks = physical.run_geometry_checks(params, members, plates, welds)

    # Connection notes come from what the checker found, never from a claim.
    problems: Dict[str, List[str]] = {}
    for c in checks.contacts:
        for mark in (c.piece_a, c.piece_b):
            other = c.piece_b if mark == c.piece_a else c.piece_a
            if c.result == "GAP":
                problems.setdefault(mark, []).append(
                    f"does NOT reach {other} (gap {c.gap:.2f} in)")
            elif c.result == "KNIFE_EDGE":
                problems.setdefault(mark, []).append(
                    f"barely touches {other} ({c.min_contact_dim:.2f} in)")
    for part in list(members) + list(plates):
        bad = problems.get(part.piece_mark)
        if not bad:
            continue
        text = "  CHECK: " + "; ".join(sorted(set(bad))) + "."
        if isinstance(part, Member):
            part.notes = (part.notes + text).strip()
        else:
            part.cut_notes = (part.cut_notes + text).strip()

    # -------------------------------------------------------------
    # 7. BOM AND CUT LIST - straight off the actual pieces above
    # -------------------------------------------------------------
    bom_rows: List[BomRow] = []
    cut_list_rows: List[CutListRow] = []
    total_weight = 0.0
    ramp_weight = 0.0

    for m in members:
        total_weight += m.total_weight
        if m.assembly == "RAMP":
            ramp_weight += m.total_weight
        length_note = (f"CUT TO FIT - APPROX. {fraction_text(m.length, 8)}"
                       if m.field_fit else "")
        bom_rows.append(BomRow(
            piece_mark=m.piece_mark, description=m.description,
            assembly=m.assembly, shape=m.section.split(" ")[0], size=m.section,
            grade=m.grade, cut_length=m.length, quantity=m.quantity,
            unit_weight=m.unit_weight, total_weight=m.total_weight,
            field_fit=m.field_fit,
            notes=(length_note + "  " + m.notes).strip()))
        cut_notes = length_note or m.cut_type
        if m.cut_angle_right:
            cut_notes += f" (bevel the back end about {m.cut_angle_right:.0f} deg)"
        if m.notes:
            cut_notes += f" - {m.notes}"
        cut_list_rows.append(CutListRow(
            piece_mark=m.piece_mark, section=m.section, grade=m.grade,
            cut_length=m.length, quantity=m.quantity, cut_type=m.cut_type,
            cut_angle_left=m.cut_angle_left, cut_angle_right=m.cut_angle_right,
            field_fit=m.field_fit, notes=cut_notes))

    for pl in plates:
        total_weight += pl.total_weight
        if pl.assembly == "RAMP":
            ramp_weight += pl.total_weight
        bom_rows.append(BomRow(
            piece_mark=pl.piece_mark, description=pl.description,
            assembly=pl.assembly, shape="PLATE",
            size=f"{pl.thickness} in x {pl.width:.2f} in x {pl.length:.2f} in",
            grade=pl.grade, cut_length=pl.length, quantity=pl.quantity,
            unit_weight=pl.unit_weight, total_weight=pl.total_weight,
            notes=pl.cut_notes))
        cut_list_rows.append(CutListRow(
            piece_mark=pl.piece_mark, section=pl.material, grade=pl.grade,
            cut_length=pl.length, quantity=pl.quantity, cut_type="PLATE_PROFILE",
            notes=f"Cut {pl.width:.2f} x {pl.length:.2f} in - {pl.cut_notes}"))

    structural = calculate_structural_checks(params, round(total_weight, 1),
                                             round(ramp_weight, 1))

    # Deployed ramp angle. The pin sits a little above the deck and the ramp is
    # 2 in deep, so the tip touches down a bit shallower than height / length.
    pin_above_ground = params.deck_height + hg["pin_z"]
    ramp_angle_deg = round(math.degrees(math.asin(
        min(1.0, max(0.0, (pin_above_ground - 2.0) / r_len)))), 1)

    return {
        "parameters": params,
        "provenance": get_project_provenance(params),
        "members": members,
        "plates": plates,
        "welds": welds,
        "holes": holes,
        "hinge": hg,
        "bom": [b.model_dump() for b in bom_rows],
        "cut_list": [c.model_dump() for c in cut_list_rows],
        "total_carrier_weight": round(total_weight, 1),
        "ramp_weight": round(ramp_weight, 1),
        "structural": structural.model_dump(),
        "ramp_angle_deg": ramp_angle_deg,
        "fabrication_sequence": fabrication_sequence(),
        "geometry_check_report": checks,
    }
