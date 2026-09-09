"""
Physical geometry engine for the Z Spray Carrier fabrication model.

This module answers one question and nothing else:

    "Do these pieces of steel actually touch each other in the real world?"

It works on the real physical envelope of every member and plate -- outside
dimensions, wall faces, plate thickness -- not on centrelines and not on notes.
A comment that says "ties into C2" proves nothing here; only overlapping steel
in X, Y and Z counts as a connection.

Nothing in this module adjusts geometry to make a check pass. If the carrier as
modelled cannot be built, the checks say so.
"""

import math
from typing import List, Dict, Any, Tuple, Optional

from models import (
    BoxBounds, Member, Plate, Weld, ProjectParameters, StatusEnum,
    ContactCheck, InterferenceCheck, EnvelopeResult,
    HingeCollision, HingeRotationResult, MachineFitResult, GeometryCheckReport,
)

# ---------------------------------------------------------------------------
# Tolerances (inches)
# ---------------------------------------------------------------------------
# Two faces closer together than this are treated as touching, not as a gap.
TOUCH_TOL = 0.010
# A structural weld needs a real bearing face. Anything narrower than this in
# either direction is a knife-edge and cannot be welded as a load path.
MIN_CONTACT_DIM = 0.500
# Minimum weldable contact patch.
MIN_CONTACT_AREA = 0.750
# Solid interpenetration deeper than this is reported.
MIN_PENETRATION = 0.010
# Overlap shallower than this is a trim-to-fit item at the bench rather than a
# structural clash (e.g. expanded metal running into the guide's upstand).
MINOR_PENETRATION = 0.250
# The shortest bead worth calling a structural weld. If two pieces touch along
# at least this much, a fabricator can run a fillet there - that is a real
# joint, whether the pieces lap face to face or just sit against each other in
# a corner. Chasing a "contact patch" instead of a weld length is what made the
# old checker call ordinary trailer joints failures.
MIN_WELD_RUN = 1.000

# Ramp rotation angles to sweep, degrees from the flat/loading position.
DEFAULT_ROTATION_ANGLES = [0.0, 5.0, 15.0, 30.0, 45.0, 60.0, 75.0, 85.0, 90.0]


# ---------------------------------------------------------------------------
# Box construction
# ---------------------------------------------------------------------------

def box_from_extents(x1: float, x2: float, y1: float, y2: float,
                     z1: float, z2: float) -> BoxBounds:
    return BoxBounds(
        min_x=min(x1, x2), max_x=max(x1, x2),
        min_y=min(y1, y2), max_y=max(y1, y2),
        min_z=min(z1, z2), max_z=max(z1, z2),
    )


def member_box(m: Member) -> BoxBounds:
    """Real outside envelope of a linear member, from its section size."""
    sw = m.section_width if m.section_width else 2.0
    sd = m.section_depth if m.section_depth else 2.0
    x1, x2 = sorted([m.start_pt.x, m.end_pt.x])
    y1, y2 = sorted([m.start_pt.y, m.end_pt.y])
    z1, z2 = sorted([m.start_pt.z, m.end_pt.z])
    axis = (m.orientation or "X").upper()
    if axis == "X":
        # Runs along X; section occupies width in Y and depth in Z.
        return box_from_extents(x1, x2, y1 - sw / 2.0, y2 + sw / 2.0,
                                z1 - sd / 2.0, z2 + sd / 2.0)
    if axis == "Y":
        # Runs along Y; section occupies width in X and depth in Z.
        return box_from_extents(x1 - sw / 2.0, x2 + sw / 2.0, y1, y2,
                                z1 - sd / 2.0, z2 + sd / 2.0)
    # Runs along Z.
    return box_from_extents(x1 - sw / 2.0, x2 + sw / 2.0,
                            y1 - sd / 2.0, y2 + sd / 2.0, z1, z2)


def plate_box(p: Plate) -> Optional[BoxBounds]:
    """
    Real outside envelope of a plate part.

    Formed parts (brake-bent guides) carry an explicit envelope because their
    folded shape is not a flat rectangle.
    """
    if p.bbox_override is not None:
        return p.bbox_override
    if p.origin is None:
        return None
    dims = {
        (p.length_axis or "X").upper(): p.length,
        (p.width_axis or "Y").upper(): p.width,
        (p.normal_axis or "Z").upper(): p.thickness,
    }
    if len(dims) != 3:
        return None
    ox, oy, oz = p.origin.x, p.origin.y, p.origin.z
    return box_from_extents(ox, ox + dims["X"], oy, oy + dims["Y"],
                            oz, oz + dims["Z"])


def collect_boxes(members: List[Member],
                  plates: List[Plate]) -> Tuple[Dict[str, BoxBounds], List[str]]:
    """Returns {piece_mark: envelope} plus the marks that have no position."""
    boxes: Dict[str, BoxBounds] = {}
    unpositioned: List[str] = []
    for m in members:
        boxes[m.piece_mark] = member_box(m)
    for p in plates:
        b = plate_box(p)
        if b is None:
            unpositioned.append(p.piece_mark)
        else:
            boxes[p.piece_mark] = b
    return boxes, unpositioned


# ---------------------------------------------------------------------------
# Contact classification
# ---------------------------------------------------------------------------

def _axis_overlap(a_min: float, a_max: float,
                  b_min: float, b_max: float) -> float:
    """Positive = interpenetration, 0 = faces touching, negative = clear gap."""
    return min(a_max, b_max) - max(a_min, b_min)


def classify_contact(a: BoxBounds, b: BoxBounds,
                     gov_a: float = 0.0, gov_b: float = 0.0) -> Dict[str, Any]:
    """
    Decide what kind of physical relationship two envelopes have.

    FACE_CONTACT   - they lap on a real face
    TANGENT_FILLET - they sit against each other with a long run of weld
                     available (a tube in a corner, a stop welded on a deck,
                     a hinge barrel against a cross tube). Perfectly normal.
    KNIFE_EDGE     - they only graze: nothing to weld along
    GAP            - they do not touch at all
    INTERFERENCE   - they occupy the same space
    """
    ox = _axis_overlap(a.min_x, a.max_x, b.min_x, b.max_x)
    oy = _axis_overlap(a.min_y, a.max_y, b.min_y, b.max_y)
    oz = _axis_overlap(a.min_z, a.max_z, b.min_z, b.max_z)
    ovs = [ox, oy, oz]
    worst = min(ovs)

    base = {"overlap_x": round(ox, 4), "overlap_y": round(oy, 4),
            "overlap_z": round(oz, 4)}

    if worst < -TOUCH_TOL:
        return {**base, "gap": round(-worst, 4), "penetration": 0.0,
                "contact_area": 0.0, "min_contact_dim": 0.0, "weld_run": 0.0,
                "result": "GAP"}

    clamped = [max(0.0, v) for v in ovs]
    patch = sorted(clamped, reverse=True)[:2]
    area = patch[0] * patch[1]
    min_dim = min(patch)
    weld_run = max(clamped)

    if worst > MIN_PENETRATION:
        return {**base, "gap": 0.0, "penetration": round(worst, 4),
                "contact_area": round(area, 4),
                "min_contact_dim": round(min_dim, 4),
                "weld_run": round(weld_run, 4), "result": "INTERFERENCE"}

    # A part fully engaged across the joint - the contact is as wide as that
    # part actually is - is a sound joint however thin the part is.
    governing = min(v for v in (gov_a, gov_b) if v > 0) if (gov_a > 0 or gov_b > 0) else 0.0
    fully_engaged = governing > 0 and min_dim >= governing - TOUCH_TOL

    if fully_engaged or (min_dim >= MIN_CONTACT_DIM and area >= MIN_CONTACT_AREA):
        result = "FACE_CONTACT"
    elif weld_run >= MIN_WELD_RUN:
        result = "TANGENT_FILLET"
    else:
        result = "KNIFE_EDGE"

    return {**base, "gap": 0.0, "penetration": 0.0,
            "contact_area": round(area, 4),
            "min_contact_dim": round(min_dim, 4),
            "weld_run": round(weld_run, 4), "result": result}


def governing_dims(members: List[Member],
                   plates: List[Plate]) -> Dict[str, float]:
    """
    Smallest real dimension each part can present at a joint.

    For a plate that is its thickness; for a member, the thinner side of its
    section. Used to tell an intended edge weld from an accidental sliver.
    """
    out: Dict[str, float] = {}
    for m in members:
        out[m.piece_mark] = min(m.section_width or 2.0, m.section_depth or 2.0)
    for p in plates:
        out[p.piece_mark] = p.thickness
    return out


def check_welds(welds: List[Weld],
                boxes: Dict[str, BoxBounds],
                gov: Optional[Dict[str, float]] = None) -> List[ContactCheck]:
    """
    Verify that every declared welded joint is backed by real steel-to-steel
    contact. A weld record is not permitted to imply a connection that the
    geometry does not support.
    """
    gov = gov or {}
    checks: List[ContactCheck] = []
    for w in welds:
        a, b = w.piece_a, w.piece_b
        box_a, box_b = boxes.get(a), boxes.get(b)
        if box_a is None or box_b is None:
            missing = a if box_a is None else b
            checks.append(ContactCheck(
                weld_id=w.weld_id, piece_a=a, piece_b=b,
                result="MISSING_GEOMETRY", passed=False,
                message=f"{missing} has no physical position, so this joint "
                        f"cannot be verified.",
            ))
            continue

        c = classify_contact(box_a, box_b, gov.get(a, 0.0), gov.get(b, 0.0))
        res = c["result"]
        passed = res in ("FACE_CONTACT", "TANGENT_FILLET", "INTERFERENCE")
        if res == "GAP":
            msg = (f"{a} and {b} never touch - clear gap of "
                   f"{c['gap']:.2f} in. This weld cannot be made.")
        elif res == "KNIFE_EDGE":
            msg = (f"{a} and {b} only graze each other - there is no run of "
                   f"steel to weld along.")
        elif res == "INTERFERENCE":
            msg = (f"{a} and {b} overlap by {c['penetration']:.2f} in. Real "
                   f"joint - notch or grind one piece to suit.")
        elif res == "TANGENT_FILLET":
            msg = (f"{a} sits against {b} - {c['weld_run']:.1f} in of fillet "
                   f"available along the joint.")
        else:
            msg = (f"{a} to {b}: good face contact, "
                   f"{c['contact_area']:.1f} sq in.")

        checks.append(ContactCheck(
            weld_id=w.weld_id, piece_a=a, piece_b=b,
            overlap_x=c["overlap_x"], overlap_y=c["overlap_y"],
            overlap_z=c["overlap_z"], gap=c["gap"],
            penetration=c["penetration"], contact_area=c["contact_area"],
            min_contact_dim=c["min_contact_dim"], weld_run=c["weld_run"],
            result=res, passed=passed, message=msg,
        ))
    return checks


def check_interference(boxes: Dict[str, BoxBounds],
                       welds: List[Weld],
                       ignore_marks: Optional[List[str]] = None,
                       nested_pairs: Optional[List[Tuple[str, str]]] = None
                       ) -> List[InterferenceCheck]:
    """
    Find every pair of parts occupying the same space.

    NESTED_FIT      - one piece is meant to slip over the other (a sleeve).
    FIT_REQUIRED    - a declared joint; notch or grind something to suit.
    UNINTENDED_CLASH- nobody meant these two to be in the same place.
    """
    ignore = set(ignore_marks or [])
    nested = {frozenset(pr) for pr in (nested_pairs or [])}
    welded_pairs = {frozenset((w.piece_a, w.piece_b)) for w in welds}
    marks = sorted(k for k in boxes if k not in ignore)
    out: List[InterferenceCheck] = []
    for i, a in enumerate(marks):
        for b in marks[i + 1:]:
            ba, bb = boxes[a], boxes[b]
            ox = _axis_overlap(ba.min_x, ba.max_x, bb.min_x, bb.max_x)
            oy = _axis_overlap(ba.min_y, ba.max_y, bb.min_y, bb.max_y)
            oz = _axis_overlap(ba.min_z, ba.max_z, bb.min_z, bb.max_z)
            pen = min(ox, oy, oz)
            if pen <= MIN_PENETRATION:
                continue
            pair = frozenset((a, b))
            if pair in nested:
                category, severity = "NESTED_FIT", "MINOR"
                message = (f"{b} slips over {a}. That is the design - it is not "
                           f"a clash.")
            elif pair in welded_pairs:
                category, severity = "FIT_REQUIRED", "MINOR"
                message = (f"{a} and {b} overlap {pen:.2f} in at a joint that is "
                           f"meant to be welded. Notch or grind to suit.")
            else:
                severity = "MINOR" if pen < MINOR_PENETRATION else "MAJOR"
                category = "UNINTENDED_CLASH"
                message = (f"{a} and {b} are in the same place ({pen:.2f} in "
                           f"deep) and nothing says they should be."
                           if severity == "MAJOR" else
                           f"{a} and {b} overlap {pen:.2f} in - trim one to fit "
                           f"at the bench.")
            out.append(InterferenceCheck(
                piece_a=a, piece_b=b,
                overlap_x=round(ox, 4), overlap_y=round(oy, 4),
                overlap_z=round(oz, 4), penetration=round(pen, 4),
                volume=round(ox * oy * oz, 3),
                has_declared_weld=pair in welded_pairs,
                category=category, severity=severity, message=message,
            ))
    out.sort(key=lambda c: (-c.penetration, c.piece_a))
    return out


# ---------------------------------------------------------------------------
# Global physical envelope
# ---------------------------------------------------------------------------

def global_envelope(boxes: Dict[str, BoxBounds],
                    width_limit: float,
                    under_truck_marks: Optional[List[str]] = None
                    ) -> EnvelopeResult:
    """
    Actual outside size of the finished carrier, measured across the steel.

    Two widths, and they mean different things:

      usable width - the deck, ramp and guides the machine rides on. THIS is
                     what the 38 in target applies to.
      total width  - everything, including the two mounting tubes that live
                     under the truck. Those are reported but they are not held
                     to the 38 in road profile; they are under the truck, not
                     sticking out past the load.
    """
    if not boxes:
        return EnvelopeResult(width_limit=width_limit)

    under = set(under_truck_marks or [])
    usable_boxes = {k: v for k, v in boxes.items() if k not in under}
    if not usable_boxes:
        usable_boxes = boxes

    def span(bx: Dict[str, BoxBounds]):
        lo = min(b.min_y for b in bx.values())
        hi = max(b.max_y for b in bx.values())
        left = sorted(k for k, b in bx.items() if b.min_y <= lo + TOUCH_TOL)
        right = sorted(k for k, b in bx.items() if b.max_y >= hi - TOUCH_TOL)
        return lo, hi, left, right

    min_y, max_y, left, right = span(boxes)
    u_lo, u_hi, u_left, u_right = span(usable_boxes)

    width = max_y - min_y
    usable = u_hi - u_lo
    usable_over = usable - width_limit
    ut_boxes = {k: v for k, v in boxes.items() if k in under}
    ut_width = (max(b.max_y for b in ut_boxes.values())
                - min(b.min_y for b in ut_boxes.values())) if ut_boxes else 0.0

    msg = (f"Deck, ramp and guides measure {usable:.2f} in across the steel. "
           + (f"Within the {width_limit:.0f} in target."
              if usable_over <= TOUCH_TOL else
              f"That is {usable_over:.2f} in over the {width_limit:.0f} in "
              f"target - widest: {', '.join(sorted(set(u_left + u_right)))}."))
    if ut_boxes:
        msg += (f" The two mounting tubes measure {ut_width:.2f} in across; they "
                f"sit under the truck and are not part of that target.")

    return EnvelopeResult(
        min_x=round(min(b.min_x for b in boxes.values()), 4),
        max_x=round(max(b.max_x for b in boxes.values()), 4),
        min_y=round(min_y, 4), max_y=round(max_y, 4),
        min_z=round(min(b.min_z for b in boxes.values()), 4),
        max_z=round(max(b.max_z for b in boxes.values()), 4),
        total_width=round(width, 4),
        total_length=round(max(b.max_x for b in boxes.values())
                           - min(b.min_x for b in boxes.values()), 4),
        width_limit=width_limit,
        within_limit=bool(usable_over <= TOUCH_TOL),
        width_over_limit=round(max(0.0, usable_over), 4),
        widest_left_pieces=left, widest_right_pieces=right,
        usable_width=round(usable, 4),
        usable_within_limit=bool(usable_over <= TOUCH_TOL),
        usable_over_limit=round(max(0.0, usable_over), 4),
        usable_left_pieces=u_left, usable_right_pieces=u_right,
        under_truck_width=round(ut_width, 4),
        under_truck_pieces=sorted(under),
        message=msg,
    )


# ---------------------------------------------------------------------------
# Ramp rotation / hinge kinematics
# ---------------------------------------------------------------------------

def _rotate_xz(x: float, z: float, px: float, pz: float,
               deg: float) -> Tuple[float, float]:
    """Rotate a point about the hinge axis in the X-Z plane (ramp swings up)."""
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    dx, dz = x - px, z - pz
    return px + dx * c - dz * s, pz + dx * s + dz * c


def _rotated_quad(b: BoxBounds, px: float, pz: float,
                  deg: float) -> List[Tuple[float, float]]:
    corners = [(b.min_x, b.min_z), (b.max_x, b.min_z),
               (b.max_x, b.max_z), (b.min_x, b.max_z)]
    return [_rotate_xz(x, z, px, pz, deg) for x, z in corners]


def _quad(b: BoxBounds) -> List[Tuple[float, float]]:
    return [(b.min_x, b.min_z), (b.max_x, b.min_z),
            (b.max_x, b.max_z), (b.min_x, b.max_z)]


def _sat_penetration(poly_a: List[Tuple[float, float]],
                     poly_b: List[Tuple[float, float]]) -> Optional[float]:
    """
    Separating-axis test for two convex polygons.
    Returns the overlap depth, or None if they are clear of each other.
    """
    best = float("inf")
    for poly in (poly_a, poly_b):
        n = len(poly)
        for i in range(n):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % n]
            ax, ay = -(y2 - y1), (x2 - x1)
            mag = math.hypot(ax, ay)
            if mag < 1e-12:
                continue
            ax, ay = ax / mag, ay / mag
            a_proj = [ax * px + ay * pz for px, pz in poly_a]
            b_proj = [ax * px + ay * pz for px, pz in poly_b]
            ov = min(max(a_proj), max(b_proj)) - max(min(a_proj), min(b_proj))
            if ov <= TOUCH_TOL:
                return None
            best = min(best, ov)
    return None if best == float("inf") else best


def hinge_rotation_check(boxes: Dict[str, BoxBounds],
                         rotating_marks: List[str],
                         pivot_x: float, pivot_z: float,
                         angles: Optional[List[float]] = None,
                         ignore_marks: Optional[List[str]] = None
                         ) -> HingeRotationResult:
    """
    Swing the ramp through its travel and look for steel hitting steel.

    Rotation is about the hinge pin axis, which lies along Y, so the problem is
    exactly two-dimensional in X-Z; the Y overlap is unaffected by the swing and
    is tested as a plain interval.
    """
    angles = angles if angles is not None else list(DEFAULT_ROTATION_ANGLES)
    ignore = set(ignore_marks or [])
    rot = [m for m in rotating_marks if m in boxes and m not in ignore]
    fixed = [m for m in boxes if m not in rotating_marks and m not in ignore]

    hits: Dict[Tuple[str, str], HingeCollision] = {}
    clear_angles: List[float] = []

    for ang in angles:
        angle_clear = True
        for rm in rot:
            rb = boxes[rm]
            rq = _rotated_quad(rb, pivot_x, pivot_z, ang)
            for fm in fixed:
                fb = boxes[fm]
                # Y is untouched by the swing.
                if _axis_overlap(rb.min_y, rb.max_y,
                                 fb.min_y, fb.max_y) <= TOUCH_TOL:
                    continue
                pen = _sat_penetration(rq, _quad(fb))
                if pen is None:
                    continue
                angle_clear = False
                key = (rm, fm)
                if key in hits:
                    hits[key].angles_deg.append(ang)
                    hits[key].max_penetration = round(
                        max(hits[key].max_penetration, pen), 4)
                else:
                    hits[key] = HingeCollision(
                        moving_piece=rm, fixed_piece=fm,
                        angles_deg=[ang], max_penetration=round(pen, 4),
                        message=(f"{rm} strikes {fm} while the ramp is being "
                                 f"raised."),
                    )
        if angle_clear:
            clear_angles.append(ang)

    collisions = sorted(hits.values(),
                        key=lambda c: (-c.max_penetration, c.moving_piece))
    for c in collisions:
        first = min(c.angles_deg)
        c.message = (f"{c.moving_piece} strikes {c.fixed_piece} "
                     f"(first contact at {first:.0f} deg, worst overlap "
                     f"{c.max_penetration:.3f}\").")

    can_rotate = len(collisions) == 0
    if can_rotate:
        msg = ("The ramp swings from flat to upright without hitting anything.")
    else:
        blocked = sorted({a for c in collisions for a in c.angles_deg})
        msg = (f"The ramp cannot be swung as drawn. "
               f"{len(collisions)} collision(s) found at "
               f"{', '.join(f'{a:.0f}' for a in blocked)} degrees.")

    return HingeRotationResult(
        pivot_x=pivot_x, pivot_z=pivot_z,
        angles_checked=angles, rotating_pieces=sorted(rot),
        collisions=collisions, clear_angles=clear_angles,
        can_rotate=can_rotate, message=msg,
    )


# ---------------------------------------------------------------------------
# Machine fit
# ---------------------------------------------------------------------------

def machine_fit_check(params: ProjectParameters,
                      boxes: Dict[str, BoxBounds],
                      guide_marks: List[str]) -> MachineFitResult:
    """
    Does the machine's running gear fit the deck?

    The guides guide the TIRES. The published 36 in machine width is a body
    dimension taken well above a 3 in guide, so it is not what has to pass
    between them - and we are not going to block a buildable carrier on it.
    Whether any bodywork brushes a guide is settled by rolling the machine on,
    which is what a shop does anyway.
    """
    notes: List[str] = []
    fit_up: List[str] = []

    tire = params.machine_rear_tire_width
    track = params.track_flat_width
    slack = (track - tire) / 2.0
    tracks_ok = slack >= 0.5
    if tracks_ok:
        notes.append(
            f"Wheel tracks are {track:.2f} in wide for a {tire:.1f} in rear "
            f"tire - {slack:.2f} in of room each side of the tire.")
    else:
        notes.append(
            f"Wheel tracks are only {track:.2f} in wide for a {tire:.1f} in "
            f"rear tire. Widen the tracks.")

    # Distance between the inside faces of the guides, reported for information.
    left_inner = right_inner = None
    for mark in guide_marks:
        b = boxes.get(mark)
        if b is None:
            continue
        if b.max_y <= 0:
            left_inner = b.max_y if left_inner is None else max(left_inner, b.max_y)
        elif b.min_y >= 0:
            right_inner = b.min_y if right_inner is None else min(right_inner, b.min_y)
    clear_width = None
    if left_inner is not None and right_inner is not None:
        clear_width = right_inner - left_inner
        notes.append(
            f"There is {clear_width:.2f} in between the inside faces of the "
            f"guides, and the guides are only {params.flared_guide_height:.0f} in "
            f"tall.")
        fit_up.append(
            "CHECK MACHINE CLEARANCE DURING FIT-UP - roll the Z-Spray on and "
            "make sure nothing on the machine rubs a guide.")

    usable = params.carrier_deck_length - params.ramp_clearance
    overhang = params.machine_length_field - usable
    if overhang > 0:
        notes.append(
            f"The machine is {params.machine_length_field:.0f} in long and the "
            f"deck is {params.carrier_deck_length:.0f} in, so it hangs about "
            f"{overhang:.0f} in over the front, forward onto the truck bed. "
            f"That is normal - the front restraint is what holds it.")

    fit_up.append(
        "CHECK DURING MACHINE FIT-UP - pull the machine forward against the "
        "wheel stops, then set the upright ramp about "
        f"{params.ramp_clearance:.0f} in behind the rear tires.")

    return MachineFitResult(
        rear_tire_width=tire,
        track_flat_width=track,
        tire_side_clearance=round(slack, 3),
        guide_clear_width=round(clear_width, 3) if clear_width is not None else None,
        tracks_fit_tires=tracks_ok,
        deck_usable_length=round(usable, 2),
        machine_length_field=params.machine_length_field,
        front_overhang=round(max(0.0, overhang), 2),
        status="PASS" if tracks_ok else "FAIL",
        notes=notes,
        fit_up_checks=fit_up,
    )


# ---------------------------------------------------------------------------
# Top level
# ---------------------------------------------------------------------------

def run_geometry_checks(params: ProjectParameters,
                        members: List[Member],
                        plates: List[Plate],
                        welds: List[Weld]) -> GeometryCheckReport:
    """Run every physical check and roll the results into one report."""
    import geometry  # local import: geometry owns the hinge layout

    boxes, unpositioned = collect_boxes(members, plates)
    gov = governing_dims(members, plates)
    hg = geometry.hinge_geometry(params)

    contacts = check_welds(welds, boxes, gov)

    # The pin lives inside the barrels, so it is not a clash. Sleeves slipped
    # over the mounting tubes are not clashes either - say so explicitly rather
    # than hiding them.
    pin_marks = [m.piece_mark for m in members
                 if m.assembly == "HINGE" and m.section.endswith("Round Bar")]
    nested_pairs = [(m.nested_over, m.piece_mark) for m in members
                    if getattr(m, "nested_over", "")]
    interferences = check_interference(boxes, welds, ignore_marks=pin_marks,
                                       nested_pairs=nested_pairs)

    under_truck = [m.piece_mark for m in members if m.assembly == "STINGER"]
    envelope = global_envelope(boxes, params.carrier_max_overall_width,
                               under_truck_marks=under_truck)

    # What actually swings: the ramp weldment. The hinge barrels and the pin all
    # share the pivot axis, so a rotation cannot move them - a round barrel spun
    # about its own centre occupies exactly the same space. They are checked for
    # static fit like every other part above; they just do not sweep.
    concentric = [m.piece_mark for m in members if m.assembly == "HINGE"]
    ramp_marks = sorted(
        [m.piece_mark for m in members if m.assembly == "RAMP"]
        + [p.piece_mark for p in plates if p.assembly == "RAMP"])
    hinge = hinge_rotation_check(
        boxes, ramp_marks,
        pivot_x=hg["pin_x"], pivot_z=hg["pin_z"],
        angles=[-20.0, -15.0, -10.0, -5.0, 0.0, 10.0, 20.0, 30.0, 45.0,
                60.0, 75.0, 85.0, 90.0],
        ignore_marks=concentric,
    )

    guide_marks = [p.piece_mark for p in plates if p.piece_mark.startswith("FG")]
    machine = machine_fit_check(params, boxes, guide_marks)

    failed_contacts = [c for c in contacts if not c.passed]
    clashes = [i for i in interferences if i.category == "UNINTENDED_CLASH"]
    major_clashes = [i for i in clashes if i.severity == "MAJOR"]

    ok = (not failed_contacts and not major_clashes
          and envelope.usable_within_limit and hinge.can_rotate
          and machine.status != "FAIL" and not unpositioned)

    summary = [
        f"{len(members)} members and {len(plates)} plates, all positioned."
        if not unpositioned else
        f"{len(unpositioned)} plates still have no position.",
        f"{len(welds)} welded joints declared; "
        + ("every one is backed by real steel-to-steel contact."
           if not failed_contacts else
           f"{len(failed_contacts)} of them are not backed by real contact."),
        (f"{len(major_clashes)} parts run into each other."
         if major_clashes else "No parts run into each other."),
        envelope.message,
        hinge.message,
        machine.notes[0] if machine.notes else "",
    ]

    return GeometryCheckReport(
        contacts=contacts,
        interferences=interferences,
        envelope=envelope,
        hinge=hinge,
        machine=machine,
        unpositioned_parts=unpositioned,
        member_count=len(members),
        plate_count=len(plates),
        positioned_member_count=len(members),
        positioned_plate_count=len(plates) - len(unpositioned),
        weld_count=len(welds),
        failed_contact_count=len(failed_contacts),
        unintended_clash_count=len(clashes),
        major_clash_count=len(major_clashes),
        overall_status="PASS" if ok else "FAIL",
        summary=[s for s in summary if s],
    )
