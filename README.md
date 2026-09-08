# Z Spray Carrier Fabricator

A parametric steel fabrication / shop-drawing generation program designed for a Z-Spray Junior carrier on a Ford F-350.

## Overview
This application generates a complete fabrication package including vector PDF shop drawings, BOM, cut list, and stock purchasing optimization. It is built as a local-first application using React/Vite for the frontend and Python/FastAPI for the parametric generation backend.

## Installation & Setup (Windows)
1. Ensure Python 3.12+ and Node.js are installed.
2. Run `Start-ZSprayCarrier.ps1` from PowerShell to bootstrap and launch the backend and frontend.

## Testing
Run `Test-ZSprayCarrier.ps1` to execute the automated backend tests covering dimension geometry, fraction conversions, BOM rollups, and stock optimization.

## Outputs
- **Z-Spray-Carrier-Shop-Drawings.pdf**: Letter-size fabrication drawings
- **BOM.csv**: Bill of materials
- **Cut-List.csv**: Cut list for fabrication
- **Purchase-List.csv**: Stock length purchase requirements

