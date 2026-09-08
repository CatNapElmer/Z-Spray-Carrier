# Z Spray Carrier Fabricator

A professional parametric steel fabrication and shop-drawing application engineered for mounting a **2026 Z-Spray Junior (Model ZSX3624)** behind a **2015 Ford F-350 flatbed** via twin Class V receivers.

---

## 🛠️ Overview & Purpose

This program is built specifically for structural steel fitters and fabricators. Rather than being a decorative 3D viewer, it operates as a full parametric CAD and engineering drafting engine that outputs complete, fabrication-ready shop packages from exact baseline datums ($X=0$ front carrier datum, $Y=0$ vehicle centerline, $Z=0$ deck running surface).

### Critical Engineering Specs
- **Carrier Footprint:** 38.00" outer width × 63.00" deck length.
- **Ramp Design:** Single rigid 61.00" ramp assembly with single hinge axis at $X=63.00"$. Zero intermediate folding joints.
- **Wheel Tracks:** Dual 12.00" flat wheel tracks with 14.00" open central cleanout gap.
- **Flared Guides:** Integrated 3.00" vertical guides with 1.50" 45° outward top flares.
- **Truck Mounts:** Twin $2\times 2\times 1/4"$ square tube stingers spaced at 38.00" center-to-center (40.00" outside-to-outside).
- **Material Selection:** ASTM A500 Grade B structural tubing ($2\times 2\times 3/16"$ & $2\times 2\times 1/4"$), ASTM A36 angle iron ($2\times 2\times 3/16"$), A36 plate gussets ($1/4"$ & $3/8"$), ASTM A513 DOM hinge barrels, and 1018 cold-finish 3/4" hinge pin.
- **Structural Safety Factor:** 3.86 (Bending stress: 11,922 psi vs. 46,000 psi yield).
- **Dead Weight:** ~317 lbs carrier dead weight (~1,465 lbs total vehicle suspended mass with machine, full liquid, and full granular fertilizer).

---

## 📐 9-Sheet Vector Shop Drawing Set (`Z-Spray-Carrier-Shop-Drawings.pdf`)

The generated vector drawing set is strictly drafted to ANSI/AWS structural steel fabrication standards on US Letter Landscape ($8.5\times 11"$) with baseline dimensions from datum $X=0$:

1. **Sheet S1: General Arrangement** - Plan view, side elevation, upright transport (90°), and deployed slope profile (16.2°).
2. **Sheet S2: Main Carrier Weldment (Plan View & Fitter Datums)** - Absolute baseline dimensions from $X=0$ for crossmembers C1 ($1"$), C2 ($18"$), C3 ($38"$), C4 ($62"$), and overall deck ($63"$).
3. **Sheet S3: Main Carrier Weldment (Elevation & Sections)** - Full elevation and Section A-A showing formed 45° flared guide, grating shelf, and underframe stinger lap.
4. **Sheet S4: Twin Receiver Mounts & Stingers** - 38" c-c twin interface, 18" provisional stinger insertion, 3" pin hole setback, and stinger gusset G1 details.
5. **Sheet S5: Ramp Weldment (Plan View)** - Single rigid ramp assembly, baseline dimensions from hinge line for RC1–RC5 crossmembers, and beveled approach plate RF1.
6. **Sheet S6: Ramp Elevation & Hinge Detail** - 90° upright transport envelope, 16.2° ground slope, and enlarged Detail B with DOM sleeve and 3/4" pin P1.
7. **Sheet S7: Individual Fabricated Parts** - Gussets G1, light guards G2 with 6.75"×2.50" oval cutouts, hinge ears G3, chain tie-down G4, wheel stops G5.
8. **Sheet S8: Material Schedule & BOM** - Complete piece schedule with mark, size, cut length, quantity, ASTM grade, and individual/total weights.
9. **Sheet S9: Stock Cutting Plan & Purchasing Optimization** - 1D linear cutting layout diagrams by stick (20-ft and 24-ft multi-length nesting, 0.125" kerf), scrap %, yield %, and raw steel order schedule.

---

## ⚠️ Provenance & Unverified Field Measurement Warnings

All dimensions in the system carry explicit provenance metadata (`derived`, `standard`, `assumed`, `field_measured`, `unverified`). 

The following items are provisional design values that **must be field-confirmed** on the 2015 Ford F-350 before cutting steel:
- **`stinger_insertion_length` (18.00"):** Measure internal receiver obstruction depth from receiver face to truck underbed obstructions.
- **`hitch_pin_hole_setback` (3.00"):** Measure distance from receiver face to centerline of the 5/8" hitch pin hole.
- **`ground_clearance` / `deck_height` (17.00"):** Confirm loaded truck bed/receiver height to verify deployed ramp angle.

---

## 💻 Local Application Architecture

- **Backend:** Python 3.12+ / FastAPI / ReportLab vector CAD canvas / Pytest
  - `geometry.py`: 3D parametric fabrication assembly model with material library and structural checks.
  - `optimizer.py`: 1D linear stock optimizer supporting multi-length raw stock and kerf modeling.
  - `drawings.py`: 9-sheet vector CAD drafting engine with architectural ticks, balloons, title blocks, and datum dimension chains.
  - `main.py`: REST API endpoints and ZIP fabrication package exporter.
- **Frontend:** React 19 / TypeScript / Vite / CSS Grid
  - 12 comprehensive parameter & fabrication panels: Project, Carrier, Tracks, Ramp, Truck Mounts, Machine & Loads, Materials, BOM, Cut List, Stock Plan, Shop Drawings, Warnings.
  - Interactive orthographic 2D SVG Plan & Elevation preview with live parametric dimension updates.
  - Provenance status indicators, parameter reset/load/save, and direct package export.

---

## 🚀 Running the Application

### Prerequisites
- Windows 10/11
- Python 3.12+ (in PATH)
- Node.js 18+ (in PATH)

### Quick Start
Run from PowerShell in the project root:
```powershell
.\Start-ZSprayCarrier.ps1
```
This starts:
- FastAPI Backend: `http://localhost:8000`
- Interactive Frontend: `http://localhost:5173`

### Running Automated Tests
Run the comprehensive test suite:
```powershell
.\Test-ZSprayCarrier.ps1
```
Or directly via Python:
```powershell
cd backend
.\.venv\Scripts\pytest test_app.py
```
*(35 test cases verifying geometry, baseline dimensions, BOM weights, stock optimization, and drawing layout)*

---

## 📦 Exported Fabrication Package

When generating an export package (via the GUI or `/api/export`), the program produces:
- `Z-Spray-Carrier-Shop-Drawings.pdf` (Complete 9-sheet vector CAD set)
- `BOM.csv` (Bill of materials piece schedule)
- `Cut-List.csv` (Cut lengths, angles, miters, piece marks)
- `Purchase-List.csv` (Raw stick order list)
- `Stock-Cutting-Plan.pdf` (1D linear nesting diagrams)
- `Project-Parameters.pdf` (Engineering parameter & provenance schedule)
- `README-FOR-FABRICATOR.txt` (Critical field measurement warnings & fitter instructions)
- `Z-Spray-Carrier-Fabrication-Package.zip` (All files bundled)
