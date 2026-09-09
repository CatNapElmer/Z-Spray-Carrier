"""
Tests for the Z Spray Carrier fabricator.

These check that the model describes a carrier a shop could actually build:
pieces that touch where they are welded, a ramp that swings, a usable width
that fits the target, and paperwork that does not present a guess as a
production dimension.

They deliberately do NOT test conditions a fabricator settles with a grinder.
"""

import os
import zipfile
import pytest
from fastapi.testclient import TestClient

from main import app
from models import ProjectParameters, StatusEnum, BoxBounds, Point3D
from geometry import (
    generate_fabrication_assembly, get_project_provenance,
    calculate_structural_checks, MATERIAL_LIBRARY, section_outside_dims,
    build_welds, hinge_barrel_positions, hinge_geometry, fabrication_sequence,
    RAMP_GUIDE_SETBACK,
)
from drawings import fraction_str, generate_shop_drawings
from optimizer import optimize_stock
import physical

client = TestClient(app)


def _assembly(**kw):
    return generate_fabrication_assembly(ProjectParameters(**kw))


def _boxes(assembly):
    boxes, _ = physical.collect_boxes(assembly["members"], assembly["plates"])
    return boxes


# ===========================================================================
# Basic plumbing
# ===========================================================================

def test_fraction_formatting():
    assert fraction_str(63.0) == '63"'
    assert fraction_str(0.75) == '3/4"'
    assert fraction_str(17.25) == '17 1/4"'
    assert fraction_str(1.25) == '1 1/4"'


def test_fraction_edge_cases_zero_and_negative():
    assert fraction_str(0.0) == '0"'
    assert fraction_str(-2.5).endswith('1/2"')


def test_api_health():
    r = client.get("/api/health")
    assert r.status_code == 200


def test_api_seed_project():
    r = client.get("/api/project/seed")
    assert r.status_code == 200
    data = r.json()
    assert data["parameters"]["carrier_deck_length"] == 63.00
    assert data["parameters"]["ramp_length"] == 61.00


def test_api_geometry_endpoint():
    r = client.post("/api/geometry", json={})
    assert r.status_code == 200
    body = r.json()
    assert len(body["bom"]) > 0
    assert body["total_carrier_weight"] > 0


def test_geometry_checks_are_exposed_over_the_api():
    r = client.post("/api/geometry-checks", json={})
    assert r.status_code == 200
    body = r.json()
    for key in ("contacts", "interferences", "envelope", "hinge", "machine",
                "overall_status"):
        assert key in body


# ===========================================================================
# The design backbone
# ===========================================================================

def test_design_backbone_dimensions():
    p = ProjectParameters()
    assert p.carrier_max_overall_width == 38.00
    assert p.carrier_deck_length == 63.00
    assert p.ramp_length == 61.00
    # "approximately 17 in" - a small practical variation is fine.
    assert 16.5 <= p.deck_height <= 18.0


def test_usable_width_is_measured_from_the_steel_and_meets_the_target():
    """The 38 in target applies to the deck / ramp / guide assembly."""
    env = _assembly()["geometry_check_report"].envelope
    assert env.usable_width == pytest.approx(38.0, abs=0.01)
    assert env.usable_within_limit is True
    assert env.usable_over_limit == 0.0


def test_under_truck_mounting_tubes_do_not_fail_the_usable_width_check():
    """
    The mounting tubes are wider than the deck because the truck's sockets are
    where they are. They live under the truck and must not be held to the road
    profile of the load.
    """
    env = _assembly()["geometry_check_report"].envelope
    assert env.under_truck_width > env.usable_width
    assert set(env.under_truck_pieces) >= {"S1-L", "S1-R", "SL-L", "SL-R"}
    # Wider overall, but the check still passes.
    assert env.total_width > 38.0
    assert env.usable_within_limit is True
    assert _assembly()["geometry_check_report"].overall_status == "PASS"


def test_widening_the_deck_does_fail_the_usable_width_check():
    """The usable-width check has to be capable of failing, or it proves nothing."""
    env = _assembly(carrier_width=40.0)["geometry_check_report"].envelope
    assert env.usable_within_limit is False
    assert env.usable_over_limit > 0


def test_wheel_tracks_comfortably_accept_the_rear_tire():
    a = _assembly()
    m = a["geometry_check_report"].machine
    p = ProjectParameters()
    assert m.track_flat_width == p.track_flat_width
    assert m.rear_tire_width == 8.50
    assert m.tire_side_clearance >= 1.0
    assert m.tracks_fit_tires is True
    assert m.status == "PASS"


def test_machine_body_width_does_not_block_the_design():
    """
    The guides guide the tires. The 36 in published body width is measured well
    above a 3 in guide and must not be treated as a pass/fail gate - it is a
    fit-up check.
    """
    a = _assembly()
    m = a["geometry_check_report"].machine
    assert m.status == "PASS"
    assert any("FIT-UP" in c.upper() for c in m.fit_up_checks)


# ===========================================================================
# Stingers: real load paths into the frame
# ===========================================================================

def test_mount_beams_exist_and_tie_both_stingers_into_the_frame():
    a = _assembly()
    marks = {m.piece_mark for m in a["members"]}
    assert {"MB1", "MB2", "MB3"} <= marks
    assert {"S1-L", "S1-R", "SL-L", "SL-R"} <= marks


def test_each_mount_beam_makes_real_contact_with_both_sleeves_and_the_rails():
    """Broad, obvious welds - not the corner of a rail."""
    a = _assembly()
    boxes = _boxes(a)
    for mb in ("MB1", "MB2", "MB3"):
        for other in ("SL-L", "SL-R", "M1-L", "M1-R", "M2-L", "M2-R"):
            c = physical.classify_contact(boxes[mb], boxes[other], 2.0, 2.0)
            assert c["result"] in ("FACE_CONTACT", "INTERFERENCE"), (
                f"{mb} to {other} came back {c['result']}")
            assert c["min_contact_dim"] >= 1.0, (
                f"{mb} to {other} only shares {c['min_contact_dim']} in")


def test_stinger_load_path_is_backed_by_geometry_not_by_notes():
    """Every declared mounting weld must be real steel-to-steel contact."""
    a = _assembly()
    checks = a["geometry_check_report"]
    mount_marks = {"MB1", "MB2", "MB3", "SL-L", "SL-R", "S1-L", "S1-R"}
    touched = [c for c in checks.contacts
               if mount_marks & {c.piece_a, c.piece_b}]
    assert touched, "the truck mount must declare welds"
    assert all(c.passed for c in touched), (
        [c.message for c in touched if not c.passed])


def test_sleeve_over_the_stinger_is_a_nested_fit_not_a_clash():
    a = _assembly()
    nested = [i for i in a["geometry_check_report"].interferences
              if i.category == "NESTED_FIT"]
    pairs = {frozenset((i.piece_a, i.piece_b)) for i in nested}
    assert frozenset(("S1-L", "SL-L")) in pairs
    assert frozenset(("S1-R", "SL-R")) in pairs
    assert all(i.severity == "MINOR" for i in nested)


def test_the_sleeve_starts_outside_the_truck_socket():
    """Nothing that goes into the truck's socket may be changed."""
    a = _assembly()
    sleeve = next(m for m in a["members"] if m.piece_mark == "SL-L")
    assert min(sleeve.start_pt.x, sleeve.end_pt.x) > 0.0


def test_mount_beam_lengths_are_cut_to_fit_not_production_dimensions():
    a = _assembly()
    for row in a["cut_list"]:
        if row["piece_mark"].startswith("MB"):
            assert row["field_fit"] is True
            assert "CUT TO FIT" in row["notes"].upper()


# ===========================================================================
# The ramp hinge
# ===========================================================================

def test_hinge_barrels_are_symmetric_and_interleaved():
    p = ProjectParameters()
    bars = hinge_barrel_positions(p)
    assert len(bars) == p.hinge_barrel_count
    # symmetric about Y = 0
    for (a0, a1, _), (b0, b1, _) in zip(bars, reversed(bars)):
        assert a0 == pytest.approx(-b1)
    owners = [o for _s, _e, o in bars]
    assert owners[0] == "Carrier" and owners[-1] == "Carrier"
    for i in range(len(owners) - 1):
        assert owners[i] != owners[i + 1], "barrels must alternate"


def test_the_deck_to_ramp_gap_is_one_barrel_diameter():
    """The single rule the whole hinge hangs on."""
    p = ProjectParameters()
    hg = hinge_geometry(p)
    assert hg["gap"] == pytest.approx(p.hinge_barrel_od)
    assert hg["pin_x"] == pytest.approx(hg["carrier_rear_x"] + p.hinge_barrel_od / 2)
    assert hg["pin_z"] == pytest.approx(p.hinge_barrel_od / 2)


def test_barrels_do_not_occupy_the_same_space_as_their_cross_tubes():
    """
    A barrel sits tangent in the corner of its cross tube. Tangent is fine;
    driven into the steel is not.
    """
    a = _assembly()
    boxes = _boxes(a)
    for m in a["members"]:
        if not m.piece_mark.startswith("HS"):
            continue
        for host in ("C4", "RC1"):
            c = physical.classify_contact(boxes[m.piece_mark], boxes[host],
                                          1.25, 2.0)
            assert c["penetration"] == 0.0, (
                f"{m.piece_mark} is driven {c['penetration']} in into {host}")
            assert c["result"] != "GAP"


def test_every_barrel_has_a_weldable_run_against_its_own_cross_tube():
    a = _assembly()
    by_pair = {(c.piece_a, c.piece_b): c for c in
               a["geometry_check_report"].contacts}
    for i, (_s, _e, owner) in enumerate(hinge_barrel_positions(ProjectParameters()),
                                        start=1):
        host = "C4" if owner == "Carrier" else "RC1"
        c = by_pair[(f"HS{i}", host)]
        assert c.passed
        assert c.weld_run >= ProjectParameters().hinge_barrel_length - 0.01


def test_hinge_bore_is_loose_enough_that_nothing_needs_reaming():
    p = ProjectParameters()
    slop = p.hinge_barrel_id - p.hinge_pin_dia
    assert 0.05 <= slop <= 0.20, "loose enough to weld, tight enough not to rattle"


def test_pin_is_long_enough_for_washers_and_clips_past_the_end_barrels():
    p = ProjectParameters()
    bars = hinge_barrel_positions(p)
    outer = max(abs(bars[0][0]), abs(bars[-1][1]))
    assert p.hinge_pin_length / 2.0 - outer >= 1.0


def test_the_ramp_actually_swings_from_deployed_to_upright():
    a = _assembly()
    h = a["geometry_check_report"].hinge
    assert h.can_rotate is True, [c.message for c in h.collisions]
    assert h.collisions == []
    # deployed (below horizontal) all the way to straight up
    assert min(h.angles_checked) <= -15.0
    assert max(h.angles_checked) == 90.0
    assert set(h.clear_angles) == set(h.angles_checked)


def test_hinge_rotation_check_can_still_fail_when_geometry_is_bad():
    """The swing test must be capable of failing, or it proves nothing."""
    boxes = {
        "RAMP": BoxBounds(min_x=63, max_x=124, min_y=-2, max_y=2,
                          min_z=-2, max_z=0),
        "WALL": BoxBounds(min_x=55, max_x=70, min_y=-2, max_y=2,
                          min_z=1, max_z=20),
    }
    r = physical.hinge_rotation_check(boxes, ["RAMP"], pivot_x=63.0, pivot_z=0.0)
    assert r.can_rotate is False
    assert r.collisions


def test_ramp_guides_are_held_back_from_the_hinge():
    """That setback is the only reason the ramp can stand fully upright."""
    a = _assembly()
    boxes = _boxes(a)
    ramp_front = hinge_geometry(ProjectParameters())["ramp_front_x"]
    assert boxes["RFG1-L"].min_x == pytest.approx(ramp_front + RAMP_GUIDE_SETBACK)
    guide = next(p for p in a["plates"] if p.piece_mark == "RFG1-L")
    assert "DO NOT RUN IT TO THE HINGE" in guide.cut_notes.upper()


def test_closing_the_guide_setback_stops_the_ramp():
    """Prove the setback is doing the work, not luck."""
    import geometry as geo
    old = geo.RAMP_GUIDE_SETBACK
    try:
        geo.RAMP_GUIDE_SETBACK = 0.0
        assert _assembly()["geometry_check_report"].hinge.can_rotate is False
    finally:
        geo.RAMP_GUIDE_SETBACK = old


# ===========================================================================
# The whole thing fits together
# ===========================================================================

def test_the_model_reports_that_it_fits_together():
    checks = _assembly()["geometry_check_report"]
    assert checks.overall_status == "PASS", checks.summary


def test_every_declared_weld_is_evaluated_and_backed_by_contact():
    a = _assembly()
    checks = a["geometry_check_report"]
    assert len(checks.contacts) == len(a["welds"])
    bad = [c.message for c in checks.contacts if not c.passed]
    assert not bad, bad


def test_no_major_unintended_clashes():
    checks = _assembly()["geometry_check_report"]
    major = [i for i in checks.interferences
             if i.category == "UNINTENDED_CLASH" and i.severity == "MAJOR"]
    assert not major, [i.message for i in major]


def test_every_part_has_a_physical_position():
    a = _assembly()
    assert a["geometry_check_report"].unpositioned_parts == []
    boxes = _boxes(a)
    for part in list(a["members"]) + list(a["plates"]):
        assert part.piece_mark in boxes


def test_a_weld_cannot_silently_imply_a_connection():
    """Move a piece away and the checker must call the joint out."""
    a = _assembly()
    boxes = _boxes(a)
    boxes["MB2"] = BoxBounds(min_x=200, max_x=202, min_y=-1, max_y=1,
                             min_z=-1, max_z=1)
    checks = physical.check_welds(a["welds"], boxes)
    broken = [c for c in checks if c.piece_a == "MB2" or c.piece_b == "MB2"]
    assert broken and all(c.result == "GAP" and not c.passed for c in broken)


def test_contact_checker_still_distinguishes_a_gap_from_contact():
    touching = physical.classify_contact(
        BoxBounds(min_x=0, max_x=10, min_y=0, max_y=2, min_z=0, max_z=2),
        BoxBounds(min_x=10, max_x=20, min_y=0, max_y=2, min_z=0, max_z=2))
    apart = physical.classify_contact(
        BoxBounds(min_x=0, max_x=10, min_y=0, max_y=2, min_z=0, max_z=2),
        BoxBounds(min_x=12, max_x=20, min_y=0, max_y=2, min_z=0, max_z=2))
    assert touching["result"] in ("FACE_CONTACT", "TANGENT_FILLET")
    assert apart["result"] == "GAP" and apart["gap"] == pytest.approx(2.0)


def test_a_piece_resting_against_another_is_a_real_joint_not_a_failure():
    """
    A tube laid in a corner, or a stop welded on a deck, touches on a line.
    You can still run a bead along it - that is ordinary fabrication and must
    not be reported as a fatal knife edge.
    """
    c = physical.classify_contact(
        BoxBounds(min_x=0, max_x=1.25, min_y=-2, max_y=2, min_z=0, max_z=1.25),
        BoxBounds(min_x=-2, max_x=0, min_y=-2, max_y=2, min_z=-2, max_z=0))
    assert c["result"] == "TANGENT_FILLET"
    assert c["weld_run"] >= 1.0
    assert c["penetration"] == 0.0


def test_a_genuine_graze_is_still_reported():
    c = physical.classify_contact(
        BoxBounds(min_x=0, max_x=0.2, min_y=0, max_y=0.2, min_z=0, max_z=0.2),
        BoxBounds(min_x=0.2, max_x=1.0, min_y=0, max_y=0.2, min_z=0, max_z=0.2))
    assert c["result"] == "KNIFE_EDGE"


def test_member_envelope_uses_outside_dimensions_not_centrelines():
    assert section_outside_dims("2x2x1/4 Tube") == (2.0, 2.0)
    assert section_outside_dims("2.5x2.5x3/16 Tube") == (2.5, 2.5)
    assert section_outside_dims("1.25x0.188 DOM Tube") == (1.25, 1.25)
    a = _assembly()
    box = _boxes(a)["M1-L"]
    assert box.max_y - box.min_y == pytest.approx(2.0)


# ===========================================================================
# No fake precision reaches the shop
# ===========================================================================

def test_no_invented_truck_measurements_remain_in_the_parameters():
    p = ProjectParameters()
    for gone in ("receiver_spacing", "receiver_outside_span",
                 "receiver_socket_outside_width", "machine_wheelbase",
                 "machine_rear_track_width", "machine_rear_tire_to_rear"):
        assert not hasattr(p, gone), f"{gone} should be gone"


def test_the_model_only_spacing_is_labelled_as_not_a_shop_dimension():
    prov = get_project_provenance(ProjectParameters())
    item = prov["stinger_spacing_model_nominal"]
    assert item.status == StatusEnum.MODEL_ONLY
    assert "FIELD FIT TO TRUCK" in item.source_note
    assert "NOT a shop dimension" in item.description


def test_truck_fit_items_are_marked_field_fit():
    prov = get_project_provenance(ProjectParameters())
    for key in ("stinger_insertion_length", "hitch_pin_hole_setback",
                "ramp_clearance"):
        assert prov[key].status == StatusEnum.FIELD_FIT


def test_hitch_pin_holes_are_transferred_from_the_truck():
    a = _assembly()
    holes = [h for h in a["holes"] if h.hole_id.endswith("PIN")]
    assert len(holes) == 2
    for h in holes:
        assert h.field_fit is True
        assert h.status == StatusEnum.FIELD_FIT
        assert "TRANSFER PIN HOLES FROM TRUCK" in h.plain_instruction.upper()


def test_field_fit_pieces_say_cut_to_fit_in_the_bom():
    a = _assembly()
    ff = [b for b in a["bom"] if b.get("field_fit")]
    assert ff
    for row in ff:
        assert "CUT TO FIT" in row["notes"].upper()


def test_shop_package_never_prints_a_stinger_spacing_dimension(tmp_path):
    """The one thing the truck settles must not appear as a number on paper."""
    p = ProjectParameters()
    a = _assembly()
    stock = optimize_stock(a, p.available_stock_lengths, p.saw_kerf)
    out = tmp_path / "pack.pdf"
    generate_shop_drawings(p, a, stock, str(out))
    raw = out.read_bytes()
    assert b"RECEIVER C-C" not in raw
    assert b"OUTSIDE SPAN" not in raw
    assert b"FIELD FIT TO TRUCK" in raw


# ===========================================================================
# BOM, cut list and purchasing
# ===========================================================================

def test_bom_and_cut_list_cover_every_piece_in_the_model():
    a = _assembly()
    model_marks = ({m.piece_mark for m in a["members"]}
                   | {p.piece_mark for p in a["plates"]})
    assert {b["piece_mark"] for b in a["bom"]} == model_marks
    assert {c["piece_mark"] for c in a["cut_list"]} == model_marks
    assert len(a["bom"]) == len(model_marks)


def test_piece_marks_are_unique():
    a = _assembly()
    marks = [b["piece_mark"] for b in a["bom"]]
    assert len(marks) == len(set(marks))


def test_bom_weights_add_up_to_the_reported_carrier_weight():
    a = _assembly()
    assert sum(b["total_weight"] for b in a["bom"]) == pytest.approx(
        a["total_carrier_weight"], abs=0.5)
    assert 300 < a["total_carrier_weight"] < 800


def test_changing_deck_length_changes_the_cut_lengths():
    short = _assembly(carrier_deck_length=55.0)
    rail = next(c for c in short["cut_list"] if c["piece_mark"] == "M1-L")
    assert rail["cut_length"] == 55.0


def test_changing_ramp_length_changes_the_cut_lengths():
    a = _assembly(ramp_length=72.0)
    rail = next(c for c in a["cut_list"] if c["piece_mark"] == "R1-L")
    assert rail["cut_length"] == 72.0


def test_purchase_list_reports_whole_sheets_not_just_what_gets_used():
    a = _assembly()
    stock = optimize_stock(a, [240.0, 288.0], 0.125)
    plate_rows = [r for r in stock["purchase_list"] if r["category"] == "PLATE"]
    assert plate_rows
    for row in plate_rows:
        assert row["quantity"] >= 1
        assert "Buy" in row["notes"]
    sheet = [r for r in plate_rows if "4x8" in r["unit_size"]]
    if sheet:
        # A full 4x8 of 3/16 plate weighs about 245 lb; report what you carry out.
        assert sheet[0]["total_purchased_weight"] > 200


def test_purchase_list_covers_the_new_stock():
    a = _assembly()
    stock = optimize_stock(a, [240.0, 288.0], 0.125)
    sections = {r["section"] for r in stock["purchase_list"]}
    assert any("2.5x2.5x3/16" in s for s in sections), "sleeve stock must be bought"
    assert any("DOM" in s for s in sections), "hinge barrel stock must be bought"


def test_stock_nesting_respects_kerf_and_never_overruns_a_stick():
    a = _assembly()
    stock = optimize_stock(a, [240.0, 288.0], 0.125)
    for stick in stock["stock_plan"]:
        assert stick["total_used"] <= stick["stock_length"] + 1e-6
        assert stick["scrap_remaining"] >= -1e-6


def test_stock_nesting_keeps_grades_apart():
    cut_list = [
        {"piece_mark": "T1", "section": "2x2x3/16 Tube",
         "grade": "ASTM A500 Gr B", "cut_length": 60.0, "quantity": 1},
        {"piece_mark": "T2", "section": "2x2x3/16 Tube",
         "grade": "ASTM A36", "cut_length": 60.0, "quantity": 1},
    ]
    opt = optimize_stock(cut_list, [240.0], saw_kerf=0.125)
    assert len(opt["stock_plan"]) == 2


# ===========================================================================
# Structural sanity - enough to catch an obviously weak carrier
# ===========================================================================

def test_structural_status_is_computed_not_hard_coded():
    a = _assembly()
    st = a["structural"]
    assert st["status"] in ("PASS", "FAIL")
    assert st["status"] == "PASS"
    assert st["yields_at_g"] >= ProjectParameters().vertical_dynamic_factor
    # Every reported number must move when the design moves.
    heavy = calculate_structural_checks(ProjectParameters(), 480.0, 160.0)
    heavier_deck = calculate_structural_checks(
        ProjectParameters(carrier_deck_length=90.0), 480.0, 160.0)
    assert heavier_deck.stinger_bending_stress_psi > heavy.stinger_bending_stress_psi


def test_an_obviously_weak_mounting_tube_is_caught():
    weak = calculate_structural_checks(
        ProjectParameters(stinger_section="2x2x3/16 Tube",
                          stinger_sleeve_section="2x2x3/16 Tube"),
        480.0, 160.0)
    assert weak.yields_at_g < ProjectParameters().vertical_dynamic_factor
    assert weak.status == "FAIL"
    assert weak.reinforcement_recommendations


def test_no_recommendation_ever_asks_to_modify_the_truck():
    """The truck is finished. Nothing may propose bracing or drilling it."""
    a = _assembly()
    banned = ("headache", "flatbed", "diagonal strut", "truck anchor",
              "drill the truck", "king-post")
    blob = " ".join(a["structural"]["reinforcement_recommendations"]
                    + a["structural"]["notes"]).lower()
    for b in banned:
        assert b not in blob, f"must not propose: {b}"


def test_hinge_is_checked_against_a_real_ramp_load():
    a = _assembly()
    h = a["structural"]["hinge_check"]
    # roughly the machine's back axle on the hinge line, plus a bounce
    assert h["design_load_lb"] > 900
    assert h["shear_planes"] == ProjectParameters().hinge_barrel_count - 1
    for key in ("pin_shear_status", "cross_tube_status", "weld_status",
                "clearance_status"):
        assert h[key] == "PASS"


def test_deployed_ramp_angle_is_sensible():
    a = _assembly()
    assert 10.0 <= a["ramp_angle_deg"] <= 20.0


# ===========================================================================
# Shop paperwork
# ===========================================================================

def test_there_is_a_build_sequence_in_plain_shop_language():
    seq = fabrication_sequence()
    assert len(seq) >= 10
    blob = " ".join(seq).upper()
    for phrase in ("TACK", "CHECK RAMP SWING BEFORE FINAL WELD",
                   "FIELD FIT TO TRUCK", "TRANSFER PIN HOLES FROM TRUCK",
                   "CHECK MACHINE CLEARANCE DURING FIT-UP"):
        assert phrase in blob
    assert _assembly()["fabrication_sequence"] == seq


def test_shop_drawings_generate(tmp_path):
    p = ProjectParameters()
    a = _assembly()
    stock = optimize_stock(a, p.available_stock_lengths, p.saw_kerf)
    out = tmp_path / "drawings.pdf"
    generate_shop_drawings(p, a, stock, str(out))
    assert out.exists() and out.stat().st_size > 20000


def test_drawings_use_plain_shop_language(tmp_path):
    p = ProjectParameters()
    a = _assembly()
    stock = optimize_stock(a, p.available_stock_lengths, p.saw_kerf)
    out = tmp_path / "drawings.pdf"
    generate_shop_drawings(p, a, stock, str(out))
    raw = out.read_bytes()
    for phrase in (b"TRUCK SIDE", b"FIELD FIT TO TRUCK",
                   b"TRANSFER PIN HOLES FROM TRUCK",
                   b"CHECK RAMP SWING BEFORE FINAL WELD"):
        assert phrase in raw, phrase


def test_drawings_carry_no_stale_hard_coded_verdict(tmp_path):
    p = ProjectParameters()
    a = _assembly()
    stock = optimize_stock(a, p.available_stock_lengths, p.saw_kerf)
    out = tmp_path / "drawings.pdf"
    generate_shop_drawings(p, a, stock, str(out))
    raw = out.read_bytes()
    assert b"FOS = 0.69" not in raw
    assert b"66,210" not in raw
    assert b"HEADACHE RACK" not in raw


def test_export_package_contains_everything_the_shop_needs():
    r = client.post("/api/export", json={})
    assert r.status_code == 200
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    zip_path = os.path.join(project_root, "output",
                            "Z-Spray-Carrier-Fabrication-Package.zip")
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        for expected in ("BOM.csv", "Cut-List.csv", "Purchase-List.csv",
                         "README-FOR-FABRICATOR.txt",
                         "Z-Spray-Carrier-Shop-Drawings.pdf"):
            assert expected in names
        readme = zf.read("README-FOR-FABRICATOR.txt").decode("utf-8")
    assert "FIELD FIT TO TRUCK" in readme
    assert "CHECK RAMP SWING BEFORE FINAL WELD" in readme
    assert "BUILD ORDER" in readme
    # no hard-coded verdicts, and nothing that would modify the truck
    assert "FOS = 0.69" not in readme
    low = readme.lower()
    for proposal in ("diagonal strut", "install strut", "brace to the truck",
                     "king-post", "truck anchor"):
        assert proposal not in low, f"must not propose: {proposal}"
    assert "the truck does not get" in low


def test_welds_name_two_real_pieces_and_have_unique_ids():
    a = _assembly()
    marks = ({m.piece_mark for m in a["members"]}
             | {p.piece_mark for p in a["plates"]})
    ids = [w.weld_id for w in a["welds"]]
    assert len(ids) == len(set(ids))
    for w in a["welds"]:
        assert w.piece_a in marks and w.piece_b in marks
        assert w.piece_a != w.piece_b
        assert w.plain_instruction


def test_truck_fit_up_welds_say_do_not_weld_yet():
    a = _assembly()
    ff = [w for w in a["welds"] if w.field_fit]
    assert ff
    assert any("TACK FIRST" in w.plain_instruction.upper() for w in ff)


def test_all_major_assemblies_are_welded_to_something():
    a = _assembly()
    welded = {w.piece_a for w in a["welds"]} | {w.piece_b for w in a["welds"]}
    for mark in ("M1-L", "C4", "RC1", "MB1", "SL-L", "HS1", "R1-L", "FG1-L"):
        assert mark in welded, f"{mark} is not welded to anything"
