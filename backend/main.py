import os
import csv
import zipfile
from typing import Dict, Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors

from models import ProjectParameters, ProjectData, StatusEnum
from geometry import generate_fabrication_assembly, get_project_provenance, calculate_structural_checks
from drawings import generate_shop_drawings, fraction_str, DraftingCanvas, draw_sheet_s9
from optimizer import optimize_stock

app = FastAPI(title="Z Spray Carrier Fabricator API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": "Z Spray Carrier Fabricator", "version": "2.0.0"}

@app.get("/api/project/seed")
def get_seed_project():
    params = ProjectParameters()
    provenance = get_project_provenance(params)
    return {
        "id": "seed-2026-z-spray",
        "name": "2026 Z-Spray Junior on 2015 Ford F-350 Flatbed",
        "parameters": params.model_dump(),
        "provenance": {k: v.model_dump() for k, v in provenance.items()}
    }

@app.post("/api/geometry")
def get_geometry(params: ProjectParameters):
    return generate_fabrication_assembly(params)

@app.post("/api/provenance")
def get_provenance(params: ProjectParameters):
    prov = get_project_provenance(params)
    return {k: v.model_dump() for k, v in prov.items()}

@app.post("/api/structural")
def get_structural_checks(params: ProjectParameters):
    assembly = generate_fabrication_assembly(params)
    return assembly["structural"]

@app.post("/api/geometry-checks")
def get_geometry_checks(params: ProjectParameters):
    """Physical contact, envelope, hinge-swing and machine-fit checks."""
    assembly = generate_fabrication_assembly(params)
    return assembly["geometry_check_report"].model_dump()

@app.post("/api/optimizer")
def get_stock_optimization(params: ProjectParameters):
    assembly = generate_fabrication_assembly(params)
    return optimize_stock(assembly, params.available_stock_lengths, params.saw_kerf)

@app.post("/api/export")
def export_package(params: ProjectParameters):
    assembly = generate_fabrication_assembly(params)
    bom = assembly["bom"]
    cut_list = assembly["cut_list"]
    stock_data = optimize_stock(assembly, params.available_stock_lengths, params.saw_kerf)
    provenance = get_project_provenance(params)
    checks = assembly["geometry_check_report"]

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    output_dir = os.path.join(project_root, "output", "Z-Spray-Carrier-Fabrication-Package")
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Full Multi-Sheet Shop Drawings (S1 through S9)
    pdf_path = os.path.join(output_dir, "Z-Spray-Carrier-Shop-Drawings.pdf")
    generate_shop_drawings(params, assembly, stock_data, pdf_path)
    
    # 2. Standalone Stock Cutting Plan PDF
    stock_pdf_path = os.path.join(output_dir, "Stock-Cutting-Plan.pdf")
    sc_c = canvas.Canvas(stock_pdf_path, pagesize=landscape(letter))
    sc_dc = DraftingCanvas(sc_c)
    draw_sheet_s9(sc_dc, params, assembly, stock_data)
    sc_c.save()
    
    # 3. Standalone Project Parameters Summary PDF
    param_pdf_path = os.path.join(output_dir, "Project-Parameters.pdf")
    pp_c = canvas.Canvas(param_pdf_path, pagesize=landscape(letter))
    pp_w, pp_h = landscape(letter)
    pp_c.setFont("Helvetica-Bold", 14)
    pp_c.drawString(50, pp_h - 50, "Z-SPRAY CARRIER - PROJECT PARAMETERS & PROVENANCE REPORT")
    pp_c.setFont("Helvetica", 8)
    pp_c.drawString(50, pp_h - 65, "Status Classifications: MEASURED | OEM | DESIGN | CALCULATED | ESTIMATED_UNVERIFIED")
    
    pp_y = pp_h - 95
    for k, item in provenance.items():
        if pp_y < 50:
            pp_c.showPage()
            pp_y = pp_h - 50
        status_color = colors.HexColor("#D90429") if item.status == StatusEnum.ESTIMATED_UNVERIFIED else colors.HexColor("#003566")
        pp_c.setFillColor(status_color)
        pp_c.setFont("Helvetica-Bold", 8)
        pp_c.drawString(50, pp_y, f"[{item.status.value}] {item.name}: {item.value} {item.units}")
        pp_c.setFillColor(colors.black)
        pp_c.setFont("Helvetica", 7.5)
        pp_c.drawString(250, pp_y, f"{item.description} - {item.source_note}")
        pp_y -= 14
    pp_c.save()
    
    # 4. BOM CSV
    bom_path = os.path.join(output_dir, "BOM.csv")
    with open(bom_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["piece_mark", "description", "assembly", "shape", "size", "grade", "cut_length", "quantity", "unit_weight", "total_weight", "notes"]
        )
        writer.writeheader()
        writer.writerows(bom)
        
    # 5. Cut List CSV
    cut_list_path = os.path.join(output_dir, "Cut-List.csv")
    with open(cut_list_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["piece_mark", "section", "grade", "cut_length", "quantity", "cut_type", "cut_angle_left", "cut_angle_right", "notes"]
        )
        writer.writeheader()
        writer.writerows(cut_list)
        
    # 6. Purchase List CSV
    purch_path = os.path.join(output_dir, "Purchase-List.csv")
    with open(purch_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["category", "section", "grade", "stick_length", "quantity", "unit_size", "total_purchased_length", "total_purchased_weight", "notes"]
        )
        writer.writeheader()
        writer.writerows(stock_data["purchase_list"])
        
    # 7. README-FOR-FABRICATOR.txt (Enumerates every unverified item)
    unverified_items = [v for v in provenance.values() if v.status == StatusEnum.ESTIMATED_UNVERIFIED]
    readme_path = os.path.join(output_dir, "README-FOR-FABRICATOR.txt")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write("================================================================================\n")
        f.write("Z SPRAY CARRIER FABRICATION PACKAGE - README FOR STEEL FITTER / FABRICATOR\n")
        f.write("================================================================================\n\n")
        f.write("PROJECT: 2026 Z Turf Equipment Z-Spray Junior (Model ZSX3624) Carrier\n")
        f.write("MOUNT:   2015 Ford F-350 Flatbed Truck Twin Receiver Hitch\n")
        f.write("UNITS:   INCHES (USCS) - Dimensions govern over graphical scaling.\n\n")
        f.write("PACKAGE CONTENTS:\n")
        f.write("  1. Z-Spray-Carrier-Shop-Drawings.pdf  - 9-Sheet Vector PDF Shop Drawing Set\n")
        f.write("  2. BOM.csv                           - Bill of Materials with weights and grades\n")
        f.write("  3. Cut-List.csv                      - Fabrication shop cut list with angles and marks\n")
        f.write("  4. Purchase-List.csv                 - Comprehensive steel, plate, grating & hardware schedule\n")
        f.write("  5. Stock-Cutting-Plan.pdf            - 1D linear nesting layout diagram by stick\n")
        f.write("  6. Project-Parameters.pdf            - Full engineering parameter and provenance list\n")
        f.write("  7. README-FOR-FABRICATOR.txt         - This verification and layout guidance document\n\n")
        f.write("--------------------------------------------------------------------------------\n")
        f.write("STRUCTURAL STATUS ADVISORY: [FAIL - UNASSISTED CANTILEVER]\n")
        f.write("--------------------------------------------------------------------------------\n")
        f.write("Under 2.0g dynamic vertical shock (1,465 lb suspended payload), cantilever bending stress\n")
        f.write("in dual 2x2x1/4 A500 Gr B stingers reaches 66,210 psi (yield strength = 46,000 psi).\n")
        f.write("FACTOR OF SAFETY = 0.69 (Target FOS = 2.00) -> STATUS: FAIL.\n")
        f.write("MANDATORY REINFORCEMENT: Install twin diagonal tubular struts from carrier rails at X=38\"\n")
        f.write("up to truck flatbed headache rack / subframe tie-down anchors (FOS > 3.0), or add an underframe\n")
        f.write("king-post truss before highway transport under load.\n\n")
        f.write("--------------------------------------------------------------------------------\n")
        f.write(f"DOES IT ACTUALLY FIT TOGETHER?  [{checks.overall_status}]\n")
        f.write("--------------------------------------------------------------------------------\n")
        f.write("These are measured from the real size of every piece of steel in the model,\n")
        f.write("not from notes or drawings.\n\n")
        for line in checks.summary:
            f.write(f"  * {line}\n")
        f.write("\n")

        bad_contacts = [c for c in checks.contacts if not c.passed]
        if bad_contacts:
            f.write("JOINTS THAT CANNOT BE WELDED AS DRAWN:\n")
            for c in bad_contacts:
                f.write(f"  [X] {c.message}\n")
            f.write("\n")

        major = [i for i in checks.interferences
                 if i.category == "UNINTENDED_CLASH" and i.severity == "MAJOR"]
        if major:
            f.write("PARTS THAT RUN INTO EACH OTHER:\n")
            for i in major:
                f.write(f"  [X] {i.message}\n")
            f.write("\n")

        if not checks.hinge.can_rotate:
            f.write("RAMP SWING:\n")
            for col in checks.hinge.collisions[:10]:
                f.write(f"  [X] {col.message}\n")
            f.write("\n")

        if checks.machine.status != "PASS":
            f.write("MACHINE FIT:\n")
            for n in checks.machine.notes:
                f.write(f"  [!] {n}\n")
            f.write("\n")

        f.write("--------------------------------------------------------------------------------\n")
        f.write("CRITICAL UNVERIFIED FIELD DIMENSIONS - MUST CONFIRM BEFORE CUTTING STEEL:\n")
        f.write("--------------------------------------------------------------------------------\n")
        for u in unverified_items:
            f.write(f"[*] {u.name.upper()} (Current provisional design: {u.value} {u.units})\n")
            f.write(f"    Description: {u.description}\n")
            f.write(f"    Requirement: {u.source_note}\n\n")
            
        f.write("--------------------------------------------------------------------------------\n")
        f.write("KEY FABRICATION CONVENTIONS & DATUMS:\n")
        f.write("--------------------------------------------------------------------------------\n")
        f.write("- FRONT DATUM (X = 0.00\"): Established at front face of front crossmember C1.\n")
        f.write("  Measure all longitudinal crossmembers directly from this front datum.\n")
        f.write("- HINGE CENTERLINE (X = 63.00\"): Centerline of the single rigid ramp pivot pin.\n")
        f.write("- RUNNING DECK ELEVATION (Z = 0.00\"): Target running surface is 17.0\" above ground.\n")
        f.write(f"- BASE FRAME WIDTH: {params.carrier_width:.2f}\" outside-to-outside of outer longitudinal tubes M1.\n")
        f.write(f"- MAXIMUM ALLOWED WIDTH: {params.carrier_max_overall_width:.2f}\" (HARD CONSTRAINT).\n")
        f.write(f"- MEASURED WIDTH OF THIS DESIGN: {checks.envelope.total_width:.2f}\" "
                f"across {', '.join(sorted(set(checks.envelope.widest_left_pieces + checks.envelope.widest_right_pieces)))}.\n")
        f.write(f"- WHEEL TRACKS: {params.track_flat_width:.2f}\" flat width per side; "
                f"{params.track_center_gap:.2f}\" clear center cleanout opening.\n")
        f.write(f"- TWIN MOUNT STINGERS: Spaced {params.receiver_spacing:.2f}\" center-to-center (UNVERIFIED - measure on the truck).\n")
        f.write("- HINGE CLEARANCE: 1-1/8\" OD x 0.172\" wall DOM tubing (0.781\" ID) provides intentional\n")
        f.write("  0.031\" (1/32\") clearance over 0.750\" pin to prevent binding under outdoor corrosion.\n")
        f.write("- WELD REQUIREMENTS: Structural tubes welded with 3/16\" fillet all around. Gussets 1/4\" fillet.\n")
        f.write("- RAMP: ONE rigid 61.00\" assembly. No intermediate folding joint.\n\n")
        f.write("================================================================================\n")
        
    # 8. Zip archive of complete fabrication package
    zip_path = os.path.join(project_root, "output", "Z-Spray-Carrier-Fabrication-Package.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(output_dir):
            for file in files:
                file_full = os.path.join(root, file)
                zf.write(file_full, arcname=os.path.basename(file_full))
                
    return FileResponse(zip_path, filename="Z-Spray-Carrier-Fabrication-Package.zip")
