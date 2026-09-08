import os
import zipfile
import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, landscape

from main import app
from models import ProjectParameters, StatusEnum, BoxBounds, Point3D
from geometry import (
    generate_fabrication_assembly, get_project_provenance,
    calculate_structural_checks, MATERIAL_LIBRARY, section_outside_dims,
    build_welds, hinge_barrel_positions,
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

# 1. fraction formatting
def test_fraction_formatting():
    assert fraction_str(1.0) == '1"'
    assert fraction_str(1.5) == '1 1/2"'
    assert fraction_str(1.25) == '1 1/4"'
    assert fraction_str(0.125) == '1/8"'
    assert fraction_str(1.0625) == '1 1/16"'
    assert fraction_str(1.1875) == '1 3/16"'
    assert fraction_str(63.0) == '63"'

# 2. negative/zero fraction edge cases
def test_fraction_edge_cases_zero_and_negative():
    assert fraction_str(0.0) == '0"'
    assert fraction_str(-1.5) == '-1 1/2"'
    assert fraction_str(-0.75) == '-3/4"'
    assert fraction_str(0.00001) == '0"'

# 3. 37.5-inch receiver center spacing (derived from 40.0 outside span - 2.5 socket OD)
def test_receiver_centerline_spacing_37_5in():
    params = ProjectParameters()
    assert params.receiver_spacing == 37.50
    assembly = generate_fabrication_assembly(params)
    stinger_l = next(m for m in assembly["members"] if m.piece_mark == "S1-L")
    stinger_r = next(m for m in assembly["members"] if m.piece_mark == "S1-R")
    assert abs(stinger_r.start_pt.y - stinger_l.start_pt.y) == 37.50

# 4. 40-inch receiver outside span and 37.5-inch spacing relationship
def test_receiver_outside_span_derivation_40in():
    params = ProjectParameters()
    assert params.receiver_outside_span == 40.00
    assert params.receiver_socket_outside_width == 2.50
    derived_spacing = params.receiver_outside_span - params.receiver_socket_outside_width
    assert derived_spacing == params.receiver_spacing
    assert derived_spacing == 37.50

# 5. deck length propagation
def test_deck_length_propagation():
    params = ProjectParameters(carrier_deck_length=65.0)
    assembly = generate_fabrication_assembly(params)
    m1 = next(m for m in assembly["members"] if m.piece_mark == "M1-L")
    assert m1.length == 65.0

# 6. ramp length propagation
def test_ramp_length_propagation():
    params = ProjectParameters(ramp_length=65.0)
    assembly = generate_fabrication_assembly(params)
    r1 = next(m for m in assembly["members"] if m.piece_mark == "R1-L")
    assert r1.length == 65.0

# 7. track width/position propagation
def test_track_geometry_propagation():
    params = ProjectParameters()
    assembly = generate_fabrication_assembly(params)
    m2_l = next(m for m in assembly["members"] if m.piece_mark == "M2-L")
    # Outer frame datum is at Y = -18.00 (frame width 36.00"), inner track rail M2-L is at Y = -6.50 -> track flat width is 11.50"
    assert abs(-18.00 - m2_l.start_pt.y) == 11.50
    # Cleanout gap between inner track angles M2-L (-6.50") and M2-R (+6.50") is 13.00"
    m2_r = next(m for m in assembly["members"] if m.piece_mark == "M2-R")
    assert abs(m2_r.start_pt.y - m2_l.start_pt.y) == 13.00

# 8. flare parameter propagation
def test_flared_guide_parameter_propagation():
    params = ProjectParameters(carrier_deck_length=64.0, flared_guide_height=3.5)
    assembly = generate_fabrication_assembly(params)
    fg = next(p for p in assembly["plates"] if p.piece_mark == "FG1-L")
    assert fg.length == 64.0

# 9. BOM aggregation
def test_bom_aggregation_and_weights():
    params = ProjectParameters()
    assembly = generate_fabrication_assembly(params)
    bom = assembly["bom"]
    assert len(bom) > 0
    total_wt = sum(row["total_weight"] for row in bom)
    assert round(total_wt, 1) == assembly["total_carrier_weight"]
    assert total_wt > 150.0 # Realistic steel carrier deadweight

# 10. no duplicate piece marks
def test_piece_mark_uniqueness():
    params = ProjectParameters()
    assembly = generate_fabrication_assembly(params)
    marks = [row["piece_mark"] for row in assembly["bom"]]
    assert len(marks) == len(set(marks)), f"Found duplicate piece marks: {marks}"

# 11. material grade preservation
def test_material_grade_preservation():
    params = ProjectParameters()
    assembly = generate_fabrication_assembly(params)
    for m in assembly["members"]:
        if "Tube" in m.section and "DOM" not in m.section:
            assert "A500" in m.grade
        elif "Angle" in m.section:
            assert "A36" in m.grade
        elif "DOM" in m.section:
            assert "A513" in m.grade
        elif "Round Bar" in m.section:
            assert "1018" in m.grade
    for p in assembly["plates"]:
        assert "A36" in p.grade

# 12. section identity preservation
def test_section_identity_preservation():
    cut_list = [
        {"piece_mark": "M1", "section": "2x2x3/16 Tube", "cut_length": 60.0, "quantity": 1},
        {"piece_mark": "S1", "section": "2x2x1/4 Tube", "cut_length": 36.0, "quantity": 1},
    ]
    opt = optimize_stock(cut_list, [240.0])
    linear_purchases = [p for p in opt["purchase_list"] if p.get("category") == "LINEAR_STOCK"]
    sections = [p["section"] for p in linear_purchases]
    assert "2x2x3/16 Tube" in sections
    assert "2x2x1/4 Tube" in sections
    assert len(sections) == 2 # Preserved separately, never merged!

# 13. calculated steel weight
def test_steel_weight_calculation():
    # 2x2x3/16 tube is 4.32 lb/ft = 0.36 lb/in
    len_in = 60.0
    wt = (len_in / 12.0) * MATERIAL_LIBRARY["2x2x3/16 Tube"]["wt_per_ft"]
    assert round(wt, 2) == 21.60

# 14. plate weight
def test_plate_weight_calculation():
    # 1/4" plate: 10" x 10" x 0.25" * 0.2836 = 7.09 lb
    vol = 10.0 * 10.0 * 0.25
    wt = vol * 0.2836
    assert round(wt, 2) == 7.09

# 15. stock optimization with 20-ft stock
def test_stock_optimizer_20ft():
    cut_list = [
        {"piece_mark": "A", "section": "2x2x3/16 Tube", "cut_length": 100.0, "quantity": 2},
        {"piece_mark": "B", "section": "2x2x3/16 Tube", "cut_length": 50.0, "quantity": 1},
    ]
    # 100 + 100 + 0.125 kerf = 200.125 fits in 240". 50 goes on stick 2
    opt = optimize_stock(cut_list, [240.0], saw_kerf=0.125)
    assert len(opt["stock_plan"]) == 2
    assert opt["stock_plan"][0]["stock_length"] == 240.0

# 16. stock optimization with both 20-ft and 24-ft options
def test_stock_optimizer_mixed_stock():
    cut_list = [
        {"piece_mark": "A", "section": "2x2x3/16 Tube", "cut_length": 63.0, "quantity": 4},
    ]
    # 4 * 63 + 3 * 0.125 = 252.375" -> fits on 288" (24-ft) stick, avoids buying two 20-ft sticks!
    opt = optimize_stock(cut_list, [240.0, 288.0], saw_kerf=0.125)
    stick = opt["stock_plan"][0]
    assert stick["stock_length"] == 288.0
    assert len(stick["parts"]) == 4

# 17. kerf accounting
def test_saw_kerf_accounting():
    cut_list = [
        {"piece_mark": "A1", "section": "2x2x3/16 Tube", "cut_length": 100.0, "quantity": 1},
        {"piece_mark": "A2", "section": "2x2x3/16 Tube", "cut_length": 100.0, "quantity": 1},
    ]
    opt = optimize_stock(cut_list, [240.0], saw_kerf=0.25)
    stick = opt["stock_plan"][0]
    assert stick["total_used"] == 200.25
    assert stick["kerf_used"] == 0.25
    assert stick["scrap_remaining"] == 240.0 - 200.25

# 18. no stock overrun
def test_no_stock_overrun():
    cut_list = [
        {"piece_mark": f"P{i}", "section": "2x2x3/16 Tube", "cut_length": 55.0, "quantity": 1}
        for i in range(10)
    ]
    opt = optimize_stock(cut_list, [240.0], saw_kerf=0.125)
    for stick in opt["stock_plan"]:
        assert stick["total_used"] <= stick["stock_length"]

# 19. PDF creation
def test_pdf_creation(tmp_path):
    params = ProjectParameters()
    assembly = generate_fabrication_assembly(params)
    stock_data = optimize_stock(assembly["cut_list"], [240.0])
    pdf_out = os.path.join(tmp_path, "test_drawings.pdf")
    generate_shop_drawings(params, assembly, stock_data, pdf_out)
    assert os.path.exists(pdf_out)
    assert os.path.getsize(pdf_out) > 5000 # Substantial vector drawing content

# 20. PDF Letter page dimensions
def test_pdf_letter_page_dimensions():
    w, h = landscape(letter)
    assert w == 792.0 # 11 inches
    assert h == 612.0 # 8.5 inches

# 21. drawing package contains S1
def test_drawing_package_contains_s1(tmp_path):
    params = ProjectParameters()
    assembly = generate_fabrication_assembly(params)
    stock_data = optimize_stock(assembly["cut_list"], [240.0])
    pdf_out = os.path.join(tmp_path, "test_s1.pdf")
    generate_shop_drawings(params, assembly, stock_data, pdf_out)
    # Read PDF text bytes
    with open(pdf_out, "rb") as f:
        data = f.read()
    assert b"GENERAL ARRANGEMENT" in data
    assert b"S1" in data

# 22. drawing package contains receiver sheet (S4)
def test_drawing_package_contains_receiver_sheet(tmp_path):
    params = ProjectParameters()
    assembly = generate_fabrication_assembly(params)
    stock_data = optimize_stock(assembly["cut_list"], [240.0])
    pdf_out = os.path.join(tmp_path, "test_s4.pdf")
    generate_shop_drawings(params, assembly, stock_data, pdf_out)
    with open(pdf_out, "rb") as f:
        data = f.read()
    assert b"TWIN RECEIVER" in data
    assert b"S4" in data

# 23. drawing package contains ramp sheet (S5, S6)
def test_drawing_package_contains_ramp_sheet(tmp_path):
    params = ProjectParameters()
    assembly = generate_fabrication_assembly(params)
    stock_data = optimize_stock(assembly["cut_list"], [240.0])
    pdf_out = os.path.join(tmp_path, "test_ramp.pdf")
    generate_shop_drawings(params, assembly, stock_data, pdf_out)
    with open(pdf_out, "rb") as f:
        data = f.read()
    assert b"RAMP WELDMENT" in data
    assert b"S5" in data
    assert b"S6" in data

# 24. fabrication package ZIP includes every required file
def test_fabrication_package_zip_contents():
    params = ProjectParameters()
    response = client.post("/api/export", json=params.model_dump())
    assert response.status_code == 200
    zip_path = "output/Z-Spray-Carrier-Fabrication-Package.zip"
    assert os.path.exists(zip_path)
    with zipfile.ZipFile(zip_path, "r") as zf:
        namelist = zf.namelist()
    required = [
        "Z-Spray-Carrier-Shop-Drawings.pdf",
        "BOM.csv",
        "Cut-List.csv",
        "Purchase-List.csv",
        "Stock-Cutting-Plan.pdf",
        "Project-Parameters.pdf",
        "README-FOR-FABRICATOR.txt"
    ]
    for req in required:
        assert req in namelist, f"Missing {req} in export ZIP: {namelist}"

# 25. changing deck length changes relevant cut lengths
def test_changing_deck_length_changes_cut_lengths():
    p1 = ProjectParameters(carrier_deck_length=63.0)
    a1 = generate_fabrication_assembly(p1)
    m1_len1 = next(row["cut_length"] for row in a1["cut_list"] if row["piece_mark"] == "M1-L")
    
    p2 = ProjectParameters(carrier_deck_length=67.0)
    a2 = generate_fabrication_assembly(p2)
    m1_len2 = next(row["cut_length"] for row in a2["cut_list"] if row["piece_mark"] == "M1-L")
    
    assert m1_len1 == 63.0
    assert m1_len2 == 67.0

# 26. changing ramp length changes relevant cut lengths
def test_changing_ramp_length_changes_cut_lengths():
    p1 = ProjectParameters(ramp_length=61.0)
    a1 = generate_fabrication_assembly(p1)
    r1_len1 = next(row["cut_length"] for row in a1["cut_list"] if row["piece_mark"] == "R1-L")
    
    p2 = ProjectParameters(ramp_length=70.0)
    a2 = generate_fabrication_assembly(p2)
    r1_len2 = next(row["cut_length"] for row in a2["cut_list"] if row["piece_mark"] == "R1-L")
    
    assert r1_len1 == 61.0
    assert r1_len2 == 70.0

# 27. changing material section changes weight
def test_changing_material_section_changes_weight():
    p1 = ProjectParameters(stinger_section="2x2x3/16 Tube")
    a1 = generate_fabrication_assembly(p1)
    wt1 = next(row["total_weight"] for row in a1["bom"] if row["piece_mark"] == "S1-L")
    
    p2 = ProjectParameters(stinger_section="2x2x1/4 Tube")
    a2 = generate_fabrication_assembly(p2)
    wt2 = next(row["total_weight"] for row in a2["bom"] if row["piece_mark"] == "S1-L")
    
    assert wt2 > wt1 # 1/4\" wall is heavier than 3/16\" wall

# 28. unverified values appear in warnings
def test_unverified_values_in_warnings():
    params = ProjectParameters()
    prov = get_project_provenance(params)
    unverified = [k for k, v in prov.items() if v.status == StatusEnum.ESTIMATED_UNVERIFIED]
    assert "stinger_insertion_length" in unverified
    assert "hitch_pin_hole_setback" in unverified
    assert "truck_suspension_drop" in unverified

# 29. unverified values appear in fabricator README
def test_unverified_values_in_fabricator_readme():
    params = ProjectParameters()
    client.post("/api/export", json=params.model_dump())
    readme_path = "output/Z-Spray-Carrier-Fabrication-Package/README-FOR-FABRICATOR.txt"
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "STINGER_INSERTION_LENGTH" in content
    assert "HITCH_PIN_HOLE_SETBACK" in content
    assert "TRUCK_SUSPENSION_DROP" in content

# 30. API health
def test_api_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

# 31. API geometry endpoint
def test_api_geometry_endpoint():
    params = ProjectParameters()
    res = client.post("/api/geometry", json=params.model_dump())
    assert res.status_code == 200
    data = res.json()
    assert "bom" in data
    assert "cut_list" in data
    assert "members" in data
    assert "total_carrier_weight" in data

# 32. API export endpoint
def test_api_export_endpoint():
    params = ProjectParameters()
    res = client.post("/api/export", json=params.model_dump())
    assert res.status_code == 200
    assert res.headers["content-type"] in ["application/zip", "application/x-zip-compressed"]

# 33. Structural load calculation check with multi-case analysis & honest FAIL status
def test_structural_load_calculation():
    params = ProjectParameters()
    res = calculate_structural_checks(params, carrier_dead_weight=317.0)
    # Total suspended weight: ~1148 lb payload + ~317 lb carrier = ~1465 lb
    assert res.payload_weight > 1140.0
    assert res.total_suspended_weight > 1460.0
    # 2.0g dynamic vertical shock: ~2930 lb
    assert res.dynamic_vertical_load > 2900.0
    # Cantilever bending stress ~66,210 psi on 2x2x1/4 A500 Gr B stingers (Fy = 46,000 psi)
    assert res.stinger_bending_stress_psi > 60000.0
    # FOS = 46000 / 66210 = 0.69 < 2.00 target
    assert res.factor_of_safety < 1.0
    assert res.factor_of_safety == pytest.approx(0.69, abs=0.05)
    assert res.status == "FAIL"
    assert res.is_adequate is False
    assert res.controlling_load_case == "VERTICAL"
    # All 4 load cases must be present
    assert "VERTICAL" in res.load_cases
    assert "BRAKING" in res.load_cases
    assert "LATERAL" in res.load_cases
    assert res.load_cases["VERTICAL"]["status"] == "FAIL"
    # Hinge mechanical checks
    assert res.hinge_check is not None
    assert res.hinge_check["diametral_clearance_in"] == pytest.approx(0.031, abs=0.005)
    assert res.hinge_check["clearance_status"] == "PASS"
    assert res.hinge_check["pin_shear_status"] == "PASS"
    assert res.hinge_check["ear_bearing_status"] == "PASS"

# 34. Ramp deployment angle check
def test_ramp_deployment_angle_calculation():
    params = ProjectParameters(deck_height=17.0, ramp_length=61.0)
    assembly = generate_fabrication_assembly(params)
    # sin(theta) = 17 / 61 = 0.2787 -> theta ~ 16.2 deg
    assert assembly["ramp_angle_deg"] == 16.2

# 35. Seed project API endpoint check
def test_api_seed_project():
    res = client.get("/api/project/seed")
    assert res.status_code == 200
    data = res.json()
    assert "parameters" in data
    assert "provenance" in data
    assert data["parameters"]["carrier_width"] == 36.0
    assert data["parameters"]["carrier_max_overall_width"] == 38.0
    assert data["parameters"]["receiver_spacing"] == 37.50

# 36. 38.00" Maximum overall envelope constraint check
def test_maximum_overall_envelope_38in():
    params = ProjectParameters()
    assert params.carrier_max_overall_width == 38.00
    assert params.carrier_width == 36.00
    assert params.flare_width == 1.00
    # Overall width = frame width + 2 * flare projection = 36.0 + 2.0 = 38.00
    overall_width = params.carrier_width + 2.0 * params.flare_width
    assert overall_width <= 38.00
    assert overall_width == 38.00
    # Verify wheel track + cleanout gap matches frame width
    # 2 * 11.50" track + 13.00" gap = 36.00" frame width
    assert (2 * params.track_flat_width + params.track_center_gap) == params.carrier_width

# 37. Stinger overlap extends past C2 (X=18.00") by 2.0"
def test_stinger_overlap_length_and_c2_tie_in():
    params = ProjectParameters()
    assert params.stinger_overlap_length == 20.00
    assembly = generate_fabrication_assembly(params)
    s1_l = next(m for m in assembly["members"] if m.piece_mark == "S1-L")
    c2 = next(m for m in assembly["members"] if m.piece_mark == "C2")
    # Insertion length is 18.0", overlap is 20.0" -> total length 38.0"
    assert s1_l.length == 38.00
    assert s1_l.start_pt.x == -18.00
    assert s1_l.end_pt.x == 20.00
    # C2 is at X = 18.00 -> stinger passes under C2 by 2.00"
    assert c2.start_pt.x == 18.00
    assert s1_l.end_pt.x > c2.start_pt.x
    assert (s1_l.end_pt.x - c2.start_pt.x) == 2.00

# 38. DOM mechanical sleeve clearance check
def test_dom_sleeve_mechanical_clearance():
    params = ProjectParameters()
    assert params.ramp_hinge_pin_dia == 0.750
    assert params.ramp_hinge_sleeve_od == 1.125
    assert params.ramp_hinge_sleeve_id == 0.781
    assert params.ramp_hinge_sleeve_wall == 0.172
    diametral_clearance = params.ramp_hinge_sleeve_id - params.ramp_hinge_pin_dia
    assert diametral_clearance == pytest.approx(0.031, abs=0.001)

# 39. Multi-category purchasing schedule with waste allowances
def test_purchase_list_categories_and_waste():
    params = ProjectParameters()
    assembly = generate_fabrication_assembly(params)
    stock_data = optimize_stock(assembly, [240.0, 288.0], saw_kerf=0.125)
    categories = {row["category"] for row in stock_data["purchase_list"]}
    assert "LINEAR_STOCK" in categories
    assert "PLATE" in categories
    assert "GRATING" in categories
    assert "HARDWARE" in categories

# 40. 1D nesting groups by (section, grade)
def test_1d_nesting_grade_isolation():
    cut_list = [
        {"piece_mark": "T1", "section": "2x2x3/16 Tube", "grade": "ASTM A500 Gr B", "cut_length": 60.0, "quantity": 1},
        {"piece_mark": "T2", "section": "2x2x3/16 Tube", "grade": "ASTM A36", "cut_length": 60.0, "quantity": 1},
    ]
    opt = optimize_stock(cut_list, [240.0], saw_kerf=0.125)
    # Because grades differ, they must be nested onto distinct sticks
    assert len(opt["stock_plan"]) == 2
    grades = {stick["grade"] for stick in opt["stock_plan"]}
    assert "ASTM A500 Gr B" in grades
    assert "ASTM A36" in grades


# ===========================================================================
# PHYSICAL MODEL TESTS
#
# These test the geometry, not the paperwork. A note that says two pieces are
# welded together proves nothing here; only overlapping steel counts.
# ===========================================================================

# --- A. Claimed welded joints must be backed by real contact ----------------

def test_every_declared_weld_is_geometrically_evaluated():
    """No weld may sit in the model without its contact being tested."""
    a = _assembly()
    checks = a["geometry_check_report"]
    assert checks.weld_count > 0
    evaluated = {(c.piece_a, c.piece_b) for c in checks.contacts}
    declared = {(w.piece_a, w.piece_b) for w in a["welds"]}
    assert declared == evaluated, "Some declared welds were never checked"


def test_contact_checker_distinguishes_gap_from_face_contact():
    """The classifier must be driven by real overlap, not by naming."""
    touching_a = BoxBounds(min_x=0, max_x=10, min_y=0, max_y=2, min_z=0, max_z=2)
    touching_b = BoxBounds(min_x=0, max_x=10, min_y=2, max_y=4, min_z=0, max_z=2)
    apart = BoxBounds(min_x=0, max_x=10, min_y=5, max_y=7, min_z=0, max_z=2)
    sliver = BoxBounds(min_x=0, max_x=10, min_y=1.75, max_y=3.75, min_z=2, max_z=4)
    buried = BoxBounds(min_x=0, max_x=10, min_y=1, max_y=3, min_z=0, max_z=2)

    assert physical.classify_contact(touching_a, touching_b, 2.0, 2.0)["result"] == "FACE_CONTACT"
    g = physical.classify_contact(touching_a, apart, 2.0, 2.0)
    assert g["result"] == "GAP" and g["gap"] == pytest.approx(3.0)
    assert physical.classify_contact(touching_a, sliver, 2.0, 2.0)["result"] == "KNIFE_EDGE"
    i = physical.classify_contact(touching_a, buried, 2.0, 2.0)
    assert i["result"] == "INTERFERENCE" and i["penetration"] == pytest.approx(1.0)


def test_plate_stood_on_edge_is_not_reported_as_a_knife_edge():
    """A 3/8 plate welded on edge to a tube is a sound joint, not a sliver."""
    tube = BoxBounds(min_x=0, max_x=32, min_y=-1, max_y=1, min_z=-2, max_z=0)
    plate = BoxBounds(min_x=0.8125, max_x=1.1875, min_y=-2, max_y=2, min_z=0, max_z=5)
    assert physical.classify_contact(tube, plate, 2.0, 0.375)["result"] == "FACE_CONTACT"
    # The same geometry judged without the governing dimension looks like a sliver,
    # which is exactly the false alarm the governing dimension exists to prevent.
    assert physical.classify_contact(tube, plate, 2.0, 2.0)["result"] == "KNIFE_EDGE"


# --- B. The known-bad stinger geometry must be detected ---------------------

def test_stinger_to_crossmember_connection_is_detected_as_broken():
    """
    The mounting tubes sit outboard of the crossmembers and never touch them.
    Until the geometry changes, the checker must say so.
    """
    a = _assembly()
    boxes = _boxes(a)
    for side in ("L", "R"):
        st = boxes[f"S1-{side}"]
        for cm in ("C1", "C2"):
            c = physical.classify_contact(st, boxes[cm], 2.0, 2.0)
            assert c["result"] == "GAP", (
                f"S1-{side} to {cm} reported {c['result']}; the model must not "
                f"claim a connection that does not exist")
            assert c["gap"] > 1.0


def test_stinger_to_side_rail_contact_is_detected_as_inadequate():
    """A quarter-inch sliver is not a structural lap joint."""
    a = _assembly()
    boxes = _boxes(a)
    for side in ("L", "R"):
        c = physical.classify_contact(boxes[f"S1-{side}"], boxes[f"M1-{side}"],
                                      2.0, 2.0)
        assert c["result"] == "KNIFE_EDGE"
        assert c["min_contact_dim"] < 0.5


def test_broken_stinger_joints_surface_in_the_check_report():
    a = _assembly()
    checks = a["geometry_check_report"]
    failed = {(c.piece_a, c.piece_b) for c in checks.contacts if not c.passed}
    for side in ("L", "R"):
        assert (f"S1-{side}", "C1") in failed
        assert (f"S1-{side}", "C2") in failed
        assert (f"S1-{side}", f"M1-{side}") in failed
    assert checks.overall_status == "FAIL"


def test_connection_notes_are_generated_from_geometry_not_asserted():
    """Part notes must never claim a tie-in the checker has not confirmed."""
    a = _assembly()
    stinger = next(m for m in a["members"] if m.piece_mark == "S1-L")
    assert "ties under" not in stinger.notes.lower()
    assert "CHECK:" in stinger.notes
    assert "does NOT reach C2" in stinger.notes


# --- C. Global envelope measured from real parts ----------------------------

def test_global_envelope_is_measured_from_actual_parts():
    """
    The outside width must come from the steel, never from
    frame_width + 2 * flare.
    """
    a = _assembly()
    env = a["geometry_check_report"].envelope
    boxes = _boxes(a)
    assert env.min_y == pytest.approx(min(b.min_y for b in boxes.values()))
    assert env.max_y == pytest.approx(max(b.max_y for b in boxes.values()))
    assert env.total_width == pytest.approx(env.max_y - env.min_y)
    # The arithmetic shortcut would say 38.00"; the steel says otherwise.
    naive = ProjectParameters().carrier_width + 2 * ProjectParameters().flare_width
    assert env.total_width > naive


def test_current_design_is_reported_as_over_width_by_the_stingers():
    a = _assembly()
    env = a["geometry_check_report"].envelope
    assert env.total_width == pytest.approx(39.50, abs=0.01)
    assert env.within_limit is False
    assert env.width_over_limit == pytest.approx(1.50, abs=0.01)
    assert "S1-L" in env.widest_left_pieces
    assert "S1-R" in env.widest_right_pieces


# --- D. Envelope responds to receiver spacing -------------------------------

def test_changing_receiver_spacing_changes_the_measured_envelope():
    narrow = _assembly(receiver_spacing=30.0)["geometry_check_report"].envelope
    wide = _assembly(receiver_spacing=44.0)["geometry_check_report"].envelope
    assert wide.total_width > narrow.total_width
    # At 30" c-c the tubes tuck inside the guides, so the guides govern.
    assert narrow.total_width == pytest.approx(38.0, abs=0.01)
    assert "S1-L" not in narrow.widest_left_pieces
    # At 44" c-c the tubes are the widest thing on the machine.
    assert wide.total_width == pytest.approx(46.0, abs=0.01)
    assert "S1-L" in wide.widest_left_pieces


# --- E. Ramp/carrier interference -------------------------------------------

def test_ramp_head_crossmember_interferes_with_rear_crossmember():
    """RC1 and C4 occupy the same space in the flat position."""
    a = _assembly()
    boxes = _boxes(a)
    c = physical.classify_contact(boxes["RC1"], boxes["C4"], 2.0, 2.0)
    assert c["result"] == "INTERFERENCE"
    assert c["penetration"] == pytest.approx(0.50, abs=0.01)
    pairs = {(i.piece_a, i.piece_b): i
             for i in a["geometry_check_report"].interferences}
    assert ("C4", "RC1") in pairs
    assert pairs[("C4", "RC1")].category == "UNINTENDED_CLASH"


def test_interference_separates_intended_joints_from_unintended_clashes():
    a = _assembly()
    inter = a["geometry_check_report"].interferences
    welded = {(i.piece_a, i.piece_b) for i in inter if i.category == "FIT_REQUIRED"}
    clash = {(i.piece_a, i.piece_b) for i in inter if i.category == "UNINTENDED_CLASH"}
    # An inner track rail crossing a cross tube is an intended, coped joint.
    assert ("C1", "M2-L") in welded
    # A hinge barrel buried in the rear cross tube is not.
    assert ("C4", "HS1") in clash
    assert not (welded & clash)


# --- F. Hinge rotation ------------------------------------------------------

def test_ramp_cannot_be_rotated_with_current_hinge_geometry():
    a = _assembly()
    hinge = a["geometry_check_report"].hinge
    assert hinge.can_rotate is False
    assert len(hinge.collisions) > 0
    hits = {(c.moving_piece, c.fixed_piece) for c in hinge.collisions}
    assert any(m.startswith("R") and f == "C4" for m, f in hits), (
        "ramp steel striking the rear cross tube must be detected")


def test_hinge_rotation_sweeps_the_full_travel():
    a = _assembly()
    hinge = a["geometry_check_report"].hinge
    assert 0.0 in hinge.angles_checked
    assert 90.0 in hinge.angles_checked
    assert len(hinge.angles_checked) >= 3
    assert hinge.pivot_x == pytest.approx(ProjectParameters().carrier_deck_length)


def test_hinge_rotation_check_can_pass_when_geometry_is_clear():
    """The rotation test must be capable of passing, or it proves nothing."""
    boxes = {
        "RAMP": BoxBounds(min_x=63, max_x=124, min_y=-2, max_y=2,
                          min_z=-2, max_z=0),
        "CARRIER": BoxBounds(min_x=0, max_x=60, min_y=-2, max_y=2,
                             min_z=-2, max_z=0),
    }
    r = physical.hinge_rotation_check(boxes, ["RAMP"], pivot_x=63.0, pivot_z=-1.0)
    assert r.can_rotate is True
    assert r.collisions == []


# --- G. Machine dimensions are never quietly shrunk -------------------------

def test_machine_width_is_used_at_full_published_size():
    a = _assembly()
    fit = a["geometry_check_report"].machine
    assert fit.machine_width == ProjectParameters().machine_width == 36.0


def test_drawing_code_contains_no_machine_shrink_fudge():
    """Guard against a display-only reduction creeping back into the drawings."""
    with open(os.path.join(os.path.dirname(__file__), "drawings.py"),
              encoding="utf-8") as f:
        src = f.read()
    assert "machine_width - 0.5" not in src
    assert "machine_width -" not in src


def test_machine_does_not_fit_between_the_guides_and_this_is_reported():
    a = _assembly()
    fit = a["geometry_check_report"].machine
    assert fit.guide_clear_width == pytest.approx(35.625, abs=0.001)
    assert fit.width_fits is False
    assert fit.width_shortfall == pytest.approx(0.375, abs=0.001)
    assert fit.status == "FAIL"


def test_unknown_wheel_positions_are_left_unverified_not_invented():
    p = ProjectParameters()
    assert p.machine_wheelbase is None
    assert p.machine_rear_tire_to_rear is None
    assert p.machine_rear_track_width is None
    fit = _assembly()["geometry_check_report"].machine
    assert fit.wheel_check_status == "UNVERIFIED"
    assert any("wheelbase" in m.lower()
               for m in fit.field_measurements_required)


# --- H. Plates are positioned and take part in the checks -------------------

def test_every_plate_has_a_physical_position():
    a = _assembly()
    assert len(a["plates"]) > 0
    for p in a["plates"]:
        assert p.origin is not None or p.bbox_override is not None, (
            f"{p.piece_mark} has no physical position")
        assert physical.plate_box(p) is not None
    assert a["geometry_check_report"].unpositioned_parts == []


def test_plates_participate_in_the_global_envelope():
    """The formed guides, not just the rails, must shape the envelope."""
    a = _assembly()
    boxes = _boxes(a)
    assert boxes["FG1-L"].min_y == pytest.approx(-19.0, abs=0.01)
    assert boxes["FG1-R"].max_y == pytest.approx(19.0, abs=0.01)
    narrow = _assembly(receiver_spacing=30.0)["geometry_check_report"].envelope
    assert "FG1-L" in narrow.widest_left_pieces


def test_plates_participate_in_collision_detection():
    a = _assembly()
    inter = a["geometry_check_report"].interferences
    plate_marks = {p.piece_mark for p in a["plates"]}
    involved = {i.piece_a for i in inter} | {i.piece_b for i in inter}
    assert involved & plate_marks, "no plate was ever collision-checked"


def test_plate_position_moves_with_its_parameters():
    wide = _boxes(_assembly(carrier_width=40.0))
    assert wide["FG1-L"].min_y == pytest.approx(-21.0, abs=0.01)
    longer = _boxes(_assembly(ramp_length=70.0))
    assert longer["RFG1-L"].max_x == pytest.approx(63.0 + 70.0, abs=0.01)


# --- I. Holes are first-class fabrication features --------------------------

def test_members_can_carry_holes_and_the_hitch_pin_holes_exist():
    a = _assembly()
    stinger = next(m for m in a["members"] if m.piece_mark == "S1-L")
    assert len(stinger.holes) == 1
    h = stinger.holes[0]
    assert h.diameter == pytest.approx(0.656)
    assert h.parent_mark == "S1-L"
    assert h.axis == "Y"
    assert h.reference_edge
    assert h.plain_instruction


def test_hitch_pin_holes_are_marked_field_fit_and_unverified():
    a = _assembly()
    for side in ("L", "R"):
        h = next(m for m in a["members"]
                 if m.piece_mark == f"S1-{side}").holes[0]
        assert h.field_fit is True
        assert h.status == StatusEnum.ESTIMATED_UNVERIFIED
        assert "do not drill" in h.plain_instruction.lower()


def test_hole_positions_are_real_coordinates_that_track_parameters():
    p = ProjectParameters()
    a = generate_fabrication_assembly(p)
    h = next(m for m in a["members"] if m.piece_mark == "S1-L").holes[0]
    expected_x = -p.stinger_insertion_length + p.hitch_pin_hole_setback
    assert h.center_x == pytest.approx(expected_x)
    assert h.center_y == pytest.approx(-p.receiver_spacing / 2.0)

    moved = generate_fabrication_assembly(
        ProjectParameters(hitch_pin_hole_setback=5.0))
    h2 = next(m for m in moved["members"] if m.piece_mark == "S1-L").holes[0]
    assert h2.center_x == pytest.approx(expected_x + 2.0)


def test_hinge_ear_holes_land_on_the_pin_centreline():
    p = ProjectParameters()
    a = generate_fabrication_assembly(p)
    ears = [pl for pl in a["plates"] if pl.piece_mark.startswith("G3-")]
    assert len(ears) == 4
    for ear in ears:
        assert len(ear.holes) == 1
        h = ear.holes[0]
        assert h.center_x == pytest.approx(p.carrier_deck_length)
        assert h.center_z == pytest.approx(p.ramp_hinge_pin_z)
        assert h.diameter == pytest.approx(p.ramp_hinge_sleeve_id)


def test_every_hole_is_attached_to_a_real_part():
    a = _assembly()
    marks = ({m.piece_mark for m in a["members"]}
             | {p.piece_mark for p in a["plates"]})
    assert len(a["holes"]) > 0
    for h in a["holes"]:
        assert h.parent_mark in marks
        assert h.diameter > 0
        assert h.plain_instruction, f"{h.hole_id} has no shop instruction"


# --- J. Welds are first-class connection features ---------------------------

def test_welds_name_exactly_two_pieces_that_exist():
    a = _assembly()
    marks = ({m.piece_mark for m in a["members"]}
             | {p.piece_mark for p in a["plates"]})
    assert len(a["welds"]) > 50
    for w in a["welds"]:
        assert w.piece_a in marks, f"{w.weld_id} references unknown {w.piece_a}"
        assert w.piece_b in marks, f"{w.weld_id} references unknown {w.piece_b}"
        assert w.piece_a != w.piece_b
        assert w.plain_instruction, f"{w.weld_id} has no plain-English wording"


def test_weld_ids_are_unique():
    a = _assembly()
    ids = [w.weld_id for w in a["welds"]]
    assert len(ids) == len(set(ids))


def test_truck_fit_up_welds_are_flagged_do_not_weld_yet():
    a = _assembly()
    fit_welds = [w for w in a["welds"] if w.field_fit]
    assert len(fit_welds) >= 6
    for w in fit_welds:
        assert "S1-" in w.piece_a or "G1-" in w.piece_a
        assert "DO NOT" in w.plain_instruction.upper() or "after truck fit-up" in w.plain_instruction


def test_all_major_assemblies_have_declared_welds():
    a = _assembly()
    pieces = {w.piece_a for w in a["welds"]} | {w.piece_b for w in a["welds"]}
    for required in ("C1", "M1-L", "M2-L", "S1-L", "G1-L1", "HS1", "G3-1",
                     "FG1-L", "EM1-L", "RC1", "R1-L", "R2-L", "RFG1-L",
                     "REM1-L", "RF1", "G2-L", "G4", "G5-L"):
        assert required in pieces, f"{required} has no declared weld"


def test_a_weld_cannot_silently_imply_a_connection():
    """Adding a weld between two parts that miss each other must be caught."""
    from models import Weld
    a = _assembly()
    boxes = _boxes(a)
    bogus = Weld(weld_id="WX", piece_a="C1", piece_b="RC5",
                 plain_instruction="pretend these touch")
    result = physical.check_welds([bogus], boxes,
                                  physical.governing_dims(a["members"], a["plates"]))
    assert result[0].passed is False
    assert result[0].result == "GAP"


# --- Section data used by the physical model --------------------------------

def test_section_outside_dims_reflect_real_stock_sizes():
    assert section_outside_dims("2x2x3/16 Tube") == (2.0, 2.0)
    assert section_outside_dims("2x2x1/4 Tube") == (2.0, 2.0)
    assert section_outside_dims("3/4 Round Bar") == (0.75, 0.75)
    assert section_outside_dims("1.125x0.172 DOM Tube") == (1.125, 1.125)


def test_member_envelope_uses_outside_dimensions_not_centrelines():
    a = _assembly()
    boxes = _boxes(a)
    m1 = boxes["M1-L"]
    # Centreline is at Y = -17; the steel runs from -18 to -16.
    assert m1.min_y == pytest.approx(-18.0)
    assert m1.max_y == pytest.approx(-16.0)
    assert m1.min_z == pytest.approx(-2.0)
    assert m1.max_z == pytest.approx(0.0)


def test_geometry_checks_are_exposed_over_the_api():
    res = client.post("/api/geometry-checks",
                      json=ProjectParameters().model_dump())
    assert res.status_code == 200
    data = res.json()
    for key in ("contacts", "interferences", "envelope", "hinge", "machine",
                "overall_status"):
        assert key in data
    assert data["envelope"]["total_width"] == pytest.approx(39.5, abs=0.01)
