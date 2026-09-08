import os
import csv
import zipfile
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from models import ProjectParameters, ProjectData
from geometry import generate_geometry
from drawings import generate_shop_drawings
from optimizer import optimize_stock

app = FastAPI(title="Z Spray Carrier Fabricator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/geometry")
def get_geometry(params: ProjectParameters):
    return generate_geometry(params)

@app.post("/api/export")
def export_package(params: ProjectParameters):
    geo = generate_geometry(params)
    bom = geo["bom"]
    
    output_dir = "output/Z-Spray-Carrier-Fabrication-Package"
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Shop Drawings
    pdf_path = os.path.join(output_dir, "Z-Spray-Carrier-Shop-Drawings.pdf")
    generate_shop_drawings(params, bom, pdf_path)
    
    # 2. BOM
    bom_path = os.path.join(output_dir, "BOM.csv")
    with open(bom_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["mark", "description", "material", "section", "grade", "cut_length", "quantity", "unit_weight", "total_weight"])
        writer.writeheader()
        writer.writerows(bom)
        
    # 3. Cut List (simplify from BOM)
    cut_list_path = os.path.join(output_dir, "Cut-List.csv")
    cut_list = []
    for item in bom:
        cut_list.append({"mark": item["mark"], "raw_section": item["section"], "cut_length": item["cut_length"], "quantity": item["quantity"], "cut_notes": ""})
    with open(cut_list_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["mark", "raw_section", "cut_length", "quantity", "cut_notes"])
        writer.writeheader()
        writer.writerows(cut_list)
        
    # 4. Stock Optimizer
    opt = optimize_stock(cut_list, [240.0])
    purch_path = os.path.join(output_dir, "Purchase-List.csv")
    with open(purch_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["section", "stick_length", "quantity"])
        writer.writeheader()
        writer.writerows(opt["purchase_list"])
        
    # 5. README
    readme_path = os.path.join(output_dir, "README-FOR-FABRICATOR.txt")
    with open(readme_path, "w") as f:
        f.write("Z Spray Carrier Fabrication Package\n")
        f.write("Units: INCHES\n")
        f.write("Note: Dimensions govern. Please verify unverified inputs before cutting steel.\n")
        
    # Zip it up
    zip_path = "output/Z-Spray-Carrier-Fabrication-Package.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for root, _, files in os.walk(output_dir):
            for file in files:
                zf.write(os.path.join(root, file), arcname=file)
                
    return FileResponse(zip_path, filename="Z-Spray-Carrier-Fabrication-Package.zip")

@app.get("/api/health")
def health_check():
    return {"status": "ok"}


