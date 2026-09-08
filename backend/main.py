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

@app.post("/api/optimizer")
def get_stock_optimization(params: ProjectParameters):
    assembly = generate_fabrication_assembly(params)
    cut_list = assembly["cut_list"]
    return optimize_stock(cut_list, params.available_stock_lengths, params.saw_kerf)

@app.post("/api/export")
def export_package(params: ProjectParameters):
    assembly = generate_fabrication_assembly(params)
    bom = assembly["bom"]
    cut_list = assembly["cut_list"]
    stock_data = optimize_stock(cut_list, params.available_stock_lengths, params.saw_kerf)
    provenance = get_project_provenance(params)
    
    output_dir = "output/Z-Spray-Carrier-Fabrication-Package"
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
            fieldnames=["piece_mark", "section", "cut_length", "quantity", "cut_type", "cut_angle_left", "cut_angle_right", "notes"]
        )
        writer.writeheader()
        writer.writerows(cut_list)
        
    # 6. Purchase List CSV
    purch_path = os.path.join(output_dir, "Purchase-List.csv")
    with open(purch_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["section", "grade", "stick_length", "quantity", "total_purchased_length", "total_purchased_weight"]
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
        f.write("MOUNT:   2015 Ford F-350 Flatbed Truck Twin Receiver Hitch (38.00\" C-C Spacing)\n")
        f.write("UNITS:   INCHES (USCS) - Dimensions govern over graphical scaling.\n\n")
        f.write("PACKAGE CONTENTS:\n")
        f.write("  1. Z-Spray-Carrier-Shop-Drawings.pdf  - 9-Sheet Vector PDF Shop Drawing Set\n")
        f.write("  2. BOM.csv                           - Bill of Materials with weights and grades\n")
        f.write("  3. Cut-List.csv                      - Fabrication shop cut list with angles and marks\n")
        f.write("  4. Purchase-List.csv                 - Raw steel purchasing schedule (sticks to order)\n")
        f.write("  5. Stock-Cutting-Plan.pdf            - 1D linear nesting layout diagram by stick\n")
        f.write("  6. Project-Parameters.pdf            - Full engineering parameter and provenance list\n")
        f.write("  7. README-FOR-FABRICATOR.txt         - This verification and layout guidance document\n\n")
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
        f.write("- FRONT DATUM (X = 0.00\"): Established at the front face of front crossmember C1.\n")
        f.write("  Measure all longitudinal crossmembers directly from this front datum.\n")
        f.write("- HINGE CENTERLINE (X = 63.00\"): Centerline of the single rigid ramp pivot pin.\n")
        f.write("- RUNNING DECK ELEVATION (Z = 0.00\"): Target running surface is 17.0\" above ground.\n")
        f.write("- OVERALL CARRIER WIDTH: 38.00\" outside-to-outside of outer longitudinal tubes M1.\n")
        f.write("- TWIN MOUNT STINGERS: Spaced exactly 38.00\" center-to-center to match F-350 receivers.\n")
        f.write("- WELD REQUIREMENTS: Structural tubes welded with 3/16\" fillet all around. Gussets 1/4\" fillet.\n")
        f.write("- RAMP: ONE rigid 61.00\" assembly. No intermediate folding joint.\n\n")
        f.write("================================================================================\n")
        
    # 8. Zip archive of complete fabrication package
    zip_path = "output/Z-Spray-Carrier-Fabrication-Package.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(output_dir):
            for file in files:
                file_full = os.path.join(root, file)
                zf.write(file_full, arcname=os.path.basename(file_full))
                
    return FileResponse(zip_path, filename="Z-Spray-Carrier-Fabrication-Package.zip")
