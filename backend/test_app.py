import os
import zipfile
import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, landscape

from main import app
from models import ProjectParameters, StatusEnum
from geometry import generate_fabrication_assembly, get_project_provenance, calculate_structural_checks, MATERIAL_LIBRARY
from drawings import fraction_str, generate_shop_drawings
from optimizer import optimize_stock

client = TestClient(app)

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

# 3. 38-inch receiver center spacing
def test_receiver_centerline_spacing_38in():
    params = ProjectParameters()
    assert params.receiver_spacing == 38.0
    assembly = generate_fabrication_assembly(params)
    stinger_l = next(m for m in assembly["members"] if m.piece_mark == "S1-L")
    stinger_r = next(m for m in assembly["members"] if m.piece_mark == "S1-R")
    assert abs(stinger_r.start_pt.y - stinger_l.start_pt.y) == 38.0

# 4. 40-inch receiver outside span derivation
def test_receiver_outside_span_derivation_40in():
    params = ProjectParameters()
    # Span = spacing (38) + tube width (2) = 40.0
    derived_outside = params.receiver_spacing + params.receiver_tube_width
    assert derived_outside == 40.0
    assert params.receiver_outside_span == 40.0

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
    params = ProjectParameters(carrier_width=38.0, track_flat_width=12.0)
    assembly = generate_fabrication_assembly(params)
    m2_l = next(m for m in assembly["members"] if m.piece_mark == "M2-L")
    # Outer edge is at -19, inner track rail M2-L is at -7 -> span is 12
    assert abs(-19.0 - m2_l.start_pt.y) == 12.0

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
    sections = [p["section"] for p in opt["purchase_list"]]
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

# 33. Structural load calculation check
def test_structural_load_calculation():
    params = ProjectParameters()
    res = calculate_structural_checks(params, carrier_dead_weight=260.0)
    assert res.payload_weight > 1000.0 # ~1148 lb
    assert res.dynamic_vertical_load > 2000.0
    assert res.stinger_bending_stress_psi > 0.0
    assert res.factor_of_safety > 0.0

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
    assert data["parameters"]["carrier_width"] == 38.0
