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
import geometry as geometry_mod
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
    pp_c.drawString(50, pp_h - 65, "MEASURED | OEM | DESIGN | CALCULATED | FIELD_FIT (set on the truck) | MODEL_ONLY (drawing coordinate, NOT a shop dimension)")
    
    pp_y = pp_h - 95
    for k, item in provenance.items():
        if pp_y < 50:
            pp_c.showPage()
            pp_y = pp_h - 50
        status_color = (colors.HexColor("#D90429")
                        if item.status in (StatusEnum.ESTIMATED_UNVERIFIED,
                                          StatusEnum.FIELD_FIT,
                                          StatusEnum.MODEL_ONLY)
                        else colors.HexColor("#003566"))
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
            fieldnames=["piece_mark", "description", "assembly", "shape", "size", "grade", "cut_length", "quantity", "unit_weight", "total_weight", "field_fit", "notes"]
        )
        writer.writeheader()
        writer.writerows(bom)
        
    # 5. Cut List CSV
    cut_list_path = os.path.join(output_dir, "Cut-List.csv")
    with open(cut_list_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["piece_mark", "section", "grade", "cut_length", "quantity", "cut_type", "cut_angle_left", "cut_angle_right", "field_fit", "notes"]
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
        
    # 7. README-FOR-FABRICATOR.txt
    field_fit_items = [v for v in provenance.values()
                       if v.status in (StatusEnum.FIELD_FIT, StatusEnum.MODEL_ONLY)]
    structural = assembly["structural"]
    hinge = assembly["hinge"]
    readme_path = os.path.join(output_dir, "README-FOR-FABRICATOR.txt")
    with open(readme_path, "w", encoding="utf-8") as f:
        w = f.write
        w("================================================================================\n")
        w("Z SPRAY CARRIER - BUILD NOTES FOR THE FABRICATOR\n")
        w("================================================================================\n\n")
        w("What this is: a welded steel carrier for a Z-Spray Junior that hangs off\n")
        w("the two receiver sockets already on the truck. The truck does not get\n")
        w("modified. Nothing bolts or welds to the flatbed or the headache rack.\n\n")
        w("All dimensions are in inches.\n\n")
        w("IN THIS PACKAGE:\n")
        w("  Z-Spray-Carrier-Shop-Drawings.pdf   drawing sheets\n")
        w("  BOM.csv                             every piece in the carrier\n")
        w("  Cut-List.csv                        what to cut and how long\n")
        w("  Purchase-List.csv                   what to buy\n")
        w("  Stock-Cutting-Plan.pdf              how to lay the cuts out on the sticks\n")
        w("  Project-Parameters.pdf              where every number came from\n")
        w("  README-FOR-FABRICATOR.txt           this file\n\n")

        w("--------------------------------------------------------------------------------\n")
        w("BUILD ORDER\n")
        w("--------------------------------------------------------------------------------\n")
        for i, step in enumerate(assembly.get("fabrication_sequence", []), start=1):
            w(f"{i:2d}. {step}\n")
        w("\n")

        w("--------------------------------------------------------------------------------\n")
        w("FIELD FIT - DO NOT MEASURE THESE OFF THE DRAWING\n")
        w("--------------------------------------------------------------------------------\n")
        w("The truck is the fixture. Slide the two mounting tubes into the truck's own\n")
        w("sockets and the spacing sets itself. There is no receiver measurement to take,\n")
        w("no socket width to check and no centreline to calculate.\n\n")
        w("  * MOUNTING TUBE SPACING ............ FIELD FIT TO TRUCK\n")
        w("  * HITCH PIN HOLES ................. TRANSFER PIN HOLES FROM TRUCK\n")
        w("  * MOUNT BEAM LENGTHS (MB1/2/3) .... CUT TO FIT between the mounting tubes\n")
        w("  * SLEEVE POSITION (SL-L / SL-R) ... slide up against the socket face\n")
        w("  * RAMP / REAR TIRE GAP ............ CHECK DURING MACHINE FIT-UP\n\n")
        for u in field_fit_items:
            w(f"[{u.status.value}] {u.name}: {u.source_note}\n")
        w("\n")

        w("--------------------------------------------------------------------------------\n")
        w("THE HINGE - THE ONLY PART WORTH READING TWICE\n")
        w("--------------------------------------------------------------------------------\n")
        w(f"One continuous {params.hinge_pin_dia:.3f} in pin. "
          f"{params.hinge_barrel_count} barrels of "
          f"{params.hinge_barrel_od:.3f} in OD tube, {params.hinge_barrel_length:.0f} in long,\n")
        w("alternating carrier / ramp. No ears, no tabs, nothing machined.\n\n")
        w(f"THE GAP BETWEEN THE DECK AND THE RAMP IS ONE BARREL DIAMETER "
          f"({params.hinge_barrel_od:.3f} in).\n")
        w("Lay a scrap of the barrel stock in the gap and that is your spacer.\n\n")
        w("Each barrel sits in the corner of its own cross tube: bottom of the barrel\n")
        w("flush with the top of the frame, back of the barrel against the cross tube\n")
        w("face. Fillet above and below, full length of the barrel.\n\n")
        w(f"The bore is {params.hinge_barrel_id:.3f} in on a {params.hinge_pin_dia:.3f} in pin. "
          f"That 1/8 in of slop is deliberate -\n")
        w("it swings freely and never needs reaming after welding.\n\n")
        w("TACK FIRST - TEST FIT BEFORE FINAL WELD.\n")
        w("CHECK RAMP SWING BEFORE FINAL WELD. If it rubs, ease the leading edge of\n")
        w("the cross tube with a grinder. Then weld it out.\n\n")

        w("--------------------------------------------------------------------------------\n")
        w(f"DOES IT ACTUALLY FIT TOGETHER?   [{checks.overall_status}]\n")
        w("--------------------------------------------------------------------------------\n")
        w("Checked against the real outside size of every piece of steel in the model.\n\n")
        for line in checks.summary:
            w(f"  * {line}\n")
        w("\n")

        bad_contacts = [c for c in checks.contacts if not c.passed]
        if bad_contacts:
            w("JOINTS THAT CANNOT BE WELDED AS DRAWN:\n")
            for c in bad_contacts:
                w(f"  [X] {c.message}\n")
            w("\n")
        major = [i for i in checks.interferences
                 if i.category == "UNINTENDED_CLASH" and i.severity == "MAJOR"]
        if major:
            w("PARTS THAT RUN INTO EACH OTHER:\n")
            for i in major:
                w(f"  [X] {i.message}\n")
            w("\n")
        if not checks.hinge.can_rotate:
            w("THE RAMP WILL NOT SWING AS DRAWN:\n")
            for col in checks.hinge.collisions[:10]:
                w(f"  [X] {col.message}\n")
            w("\n")

        w("--------------------------------------------------------------------------------\n")
        w(f"IS IT STRONG ENOUGH?   [{structural['status']}]\n")
        w("--------------------------------------------------------------------------------\n")
        for n in structural["notes"]:
            w(f"  * {n}\n")
        if structural["reinforcement_recommendations"]:
            w("\n")
            for r in structural["reinforcement_recommendations"]:
                w(f"  ! {r}\n")
        w("\n")

        w("--------------------------------------------------------------------------------\n")
        w("KEY NUMBERS\n")
        w("--------------------------------------------------------------------------------\n")
        w("  TRUCK SIDE is X = 0. RAMP SIDE is the back. Measure everything from the\n")
        w("  truck end of the side rails.\n")
        w(f"  Deck frame ................ {params.carrier_deck_length:.0f} in long, "
          f"{params.carrier_width:.0f} in wide outside the side rails\n")
        w(f"  Deck height ............... about {params.deck_height:.2f} in off the ground\n")
        w(f"  Usable width (deck, ramp, guides) ... "
          f"{checks.envelope.usable_width:.2f} in measured across the steel "
          f"(target {params.carrier_max_overall_width:.0f} in)\n")
        w(f"  Mounting tubes under the truck ...... "
          f"{checks.envelope.under_truck_width:.2f} in across - under the truck, "
          f"not part of that target\n")
        w(f"  Wheel tracks .............. {params.track_flat_width:.2f} in each, "
          f"{params.track_center_gap:.0f} in open down the middle\n")
        w(f"  Rear tire ................. {params.machine_rear_tire_size} "
          f"({params.machine_rear_tire_width:.1f} in wide) - "
          f"{checks.machine.tire_side_clearance:.2f} in of room each side\n")
        w(f"  Ramp ...................... {params.ramp_length:.0f} in, one rigid "
          f"piece, sits at about {assembly['ramp_angle_deg']:.0f} deg when down\n")
        w(f"  Ramp guides ............... start {geometry_mod.RAMP_GUIDE_SETBACK:.2f} in "
          f"back from the front of the ramp - LEAVE THAT GAP\n")
        w(f"  Hinge pin ................. {params.hinge_pin_dia:.3f} in x "
          f"{params.hinge_pin_length:.0f} in, at X = {hinge['pin_x']:.3f} in, "
          f"{hinge['pin_z']:.3f} in above the deck\n")
        w(f"  Carrier weight ............ about {assembly['total_carrier_weight']:.0f} lb "
          f"(ramp about {assembly['ramp_weight']:.0f} lb of that)\n")
        w("  Welds ..................... 3/16 fillet on frame tubes, 1/4 on the "
          "mount beams,\n                              sleeves and hinge barrels\n\n")
        for fu in checks.machine.fit_up_checks:
            w(f"  ! {fu}\n")
        w("\n================================================================================\n")

    # 8. Zip archive of complete fabrication package
    zip_path = os.path.join(project_root, "output", "Z-Spray-Carrier-Fabrication-Package.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(output_dir):
            for file in files:
                file_full = os.path.join(root, file)
                zf.write(file_full, arcname=os.path.basename(file_full))
                
    return FileResponse(zip_path, filename="Z-Spray-Carrier-Fabrication-Package.zip")
