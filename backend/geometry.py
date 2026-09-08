from typing import List, Dict, Any
import math
from models import ProjectParameters, BomRow, CutListRow

def generate_geometry(params: ProjectParameters) -> Dict[str, Any]:
    # Standard Shapes
    tube2x2 = "2x2x3/16 Tube"
    tube2x2_wt = 0.20 # approx lbs/in
    angle2x2 = "2x2x1/4 Angle"
    angle2x2_wt = 0.26 # lbs/in
    flat4 = "4x1/4 Flat"
    flat4_wt = 0.28
    
    parts = []
    
    # 1. Main Longitudinal Members (M1)
    # Outside width = 38", made of 2x2 tube
    m1_len = params.carrier_deck_length
    parts.append({"mark": "M1", "desc": "Main Deck Tube", "mat": tube2x2, "qty": 2, "len": m1_len, "wt": tube2x2_wt})
    
    # 2. Deck Crossmembers (C1)
    # Fit between M1
    c1_len = params.carrier_width - 4.0 # 2" tubes on each side
    # Front, Middle, Rear, maybe one more
    parts.append({"mark": "C1", "desc": "Deck Crossmember", "mat": tube2x2, "qty": 4, "len": c1_len, "wt": tube2x2_wt})
    
    # 3. Stingers (S1)
    # Mount to truck. Span is 38" c-c. Length say 24"
    stinger_len = 24.0
    parts.append({"mark": "S1", "desc": "Truck Stinger", "mat": "2x2x1/4 Tube", "qty": 2, "len": stinger_len, "wt": 0.26})
    
    # 4. Ramp Main Members (R1)
    r1_len = params.ramp_length
    parts.append({"mark": "R1", "desc": "Ramp Side Tube", "mat": tube2x2, "qty": 2, "len": r1_len, "wt": tube2x2_wt})
    
    # 5. Ramp Crossmembers (RC1)
    # Assume ramp is same width as carrier for simplicity
    rc1_len = params.carrier_width - 4.0
    parts.append({"mark": "RC1", "desc": "Ramp Crossmember", "mat": angle2x2, "qty": 4, "len": rc1_len, "wt": angle2x2_wt})
    
    # 6. Flared Guides (F1)
    flare_len = m1_len
    parts.append({"mark": "F1", "desc": "Wheel Guide", "mat": flat4, "qty": 2, "len": flare_len, "wt": flat4_wt})
    
    # 7. Hinge Pins (P1)
    parts.append({"mark": "P1", "desc": "Hinge Pin", "mat": "3/4 Round", "qty": 2, "len": 4.0, "wt": 0.12})
    
    # Build BOM
    bom = []
    for p in parts:
        total_wt = p["len"] * p["qty"] * p["wt"]
        bom.append({
            "mark": p["mark"],
            "description": p["desc"],
            "material": p["mat"],
            "section": p["mat"].split(" ")[0],
            "grade": "A500/A36",
            "cut_length": p["len"],
            "quantity": p["qty"],
            "unit_weight": p["wt"] * 12, # lbs/ft
            "total_weight": total_wt
        })
        
    return {"bom": bom}

