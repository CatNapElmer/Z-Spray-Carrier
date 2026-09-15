import math
from typing import List, Dict, Any, Tuple
from models import CutListRow, PurchaseRow, StockStick, StockPlanResult
from geometry import MATERIAL_LIBRARY

def _get(obj: Any, attr: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)

def optimize_stock(
    assembly_or_cuts: Any,
    stock_lengths: List[float] = [240.0, 288.0], # 20 ft and 24 ft
    saw_kerf: float = 0.125
) -> Dict[str, Any]:
    """
    Cutting Stock & Material Purchasing Optimizer.
    1. Linear Sections: Packs cut pieces into optimal commercial stock lengths (20-ft / 24-ft)
       accounting for saw kerf (0.125") while strictly separating items by (section, grade).
    2. Plate & Sheet: Aggregates required plate area by thickness and grade with 20% cutting/shear waste.
    3. Traction Grating: Aggregates expanded metal square footage with 15% cutting allowance.
    4. Bought-Out Hardware: Schedules commercial hitch pins, linchpins, shackles, and LED lamps.
    """
    if isinstance(assembly_or_cuts, dict):
        cut_list = assembly_or_cuts.get("cut_list", [])
        plates = assembly_or_cuts.get("plates", [])
        hardware = assembly_or_cuts.get("hardware", [])
    elif isinstance(assembly_or_cuts, list):
        cut_list = assembly_or_cuts
        plates = []
        hardware = []
    else:
        cut_list = []
        plates = []
        hardware = []
    
    # -------------------------------------------------------------
    # 1. LINEAR STOCK 1D NESTING
    # -------------------------------------------------------------
    linear_items = [
        item for item in cut_list
        if not _get(item, "cut_type", "").startswith("PLATE")
        and "Plate" not in _get(item, "section", "")
        and "Expanded Metal" not in _get(item, "section", "")
    ]
    
    # Group items by (section, grade) so identical sections of different grades NEVER merge
    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for item in linear_items:
        sec = _get(item, "section")
        grd = _get(item, "grade", "ASTM A500 Gr B")
        key = (sec, grd)
        if key not in grouped:
            grouped[key] = []
        qty = _get(item, "quantity", 1)
        for _ in range(qty):
            grouped[key].append({
                "piece_mark": _get(item, "piece_mark"),
                "length": float(_get(item, "cut_length")),
                "section": sec,
                "grade": grd,
                "notes": _get(item, "notes", "")
            })
            
    sorted_stock_opts = sorted(stock_lengths)
    if not sorted_stock_opts:
        sorted_stock_opts = [240.0]
        
    stock_plan: List[Dict[str, Any]] = []
    purchase_summary: Dict[Tuple[str, str], Dict[float, int]] = {}
    total_linear_purchased_wt = 0.0
    total_linear_cut_wt = 0.0
    
    global_stick_counter = 1
    
    for (section, grade), parts in grouped.items():
        if not parts:
            continue
            
        mat_info = MATERIAL_LIBRARY.get(section, {})
        wt_ft = mat_info.get("wt_per_ft", 4.0)
        
        # Sort parts descending by length (First-Fit Decreasing heuristic)
        parts_remaining = sorted(parts, key=lambda p: p["length"], reverse=True)
        
        if (section, grade) not in purchase_summary:
            purchase_summary[(section, grade)] = {sl: 0 for sl in sorted_stock_opts}
            
        while parts_remaining:
            best_waste = float("inf")
            best_packed: List[Dict[str, Any]] = []
            best_remaining: List[Dict[str, Any]] = []
            best_stock_len = sorted_stock_opts[0]
            
            for candidate_sl in sorted_stock_opts:
                temp_packed = []
                temp_rem = []
                current_used = 0.0
                
                for p in parts_remaining:
                    needed = p["length"] + (saw_kerf if temp_packed else 0.0)
                    if current_used + needed <= candidate_sl + 1e-6:
                        temp_packed.append(p)
                        current_used += needed
                    else:
                        temp_rem.append(p)
                        
                if temp_packed:
                    waste = candidate_sl - current_used
                    if waste < best_waste or (abs(waste - best_waste) < 1.0 and candidate_sl < best_stock_len):
                        best_waste = waste
                        best_packed = temp_packed
                        best_remaining = temp_rem
                        best_stock_len = candidate_sl
                        
            if not best_packed:
                p = parts_remaining.pop(0)
                best_stock_len = sorted_stock_opts[-1]
                best_packed = [p]
                best_remaining = parts_remaining
                best_waste = max(0.0, best_stock_len - p["length"])
                
            parts_remaining = best_remaining
            purchase_summary[(section, grade)][best_stock_len] += 1
            
            part_sum = sum(p["length"] for p in best_packed)
            kerf_tot = (len(best_packed) - 1) * saw_kerf if len(best_packed) > 1 else 0.0
            tot_used = part_sum + kerf_tot
            rem_scrap = max(0.0, best_stock_len - tot_used)
            eff = (part_sum / best_stock_len) * 100.0 if best_stock_len > 0 else 0.0
            
            stock_plan.append({
                "stick_id": f"STK-{global_stick_counter:02d}",
                "section": section,
                "grade": grade,
                "stock_length": best_stock_len,
                "parts": best_packed,
                "total_used": round(tot_used, 3),
                "kerf_used": round(kerf_tot, 3),
                "scrap_remaining": round(rem_scrap, 3),
                "efficiency_pct": round(eff, 1)
            })
            global_stick_counter += 1
            
            total_linear_purchased_wt += (best_stock_len / 12.0) * wt_ft
            total_linear_cut_wt += (part_sum / 12.0) * wt_ft

    # -------------------------------------------------------------
    # 2. BUILD COMPREHENSIVE PURCHASE ROWS (LINEAR, PLATE, GRATING, HARDWARE)
    # -------------------------------------------------------------
    purchase_rows: List[Dict[str, Any]] = []
    
    # Linear items
    for (section, grade), sl_dict in purchase_summary.items():
        mat_info = MATERIAL_LIBRARY.get(section, {})
        wt_ft = mat_info.get("wt_per_ft", 4.0)
        
        for sl, qty in sl_dict.items():
            if qty > 0:
                tot_len = sl * qty
                tot_wt = (tot_len / 12.0) * wt_ft
                purchase_rows.append({
                    "category": "LINEAR_STOCK",
                    "section": section,
                    "grade": grade,
                    "stick_length": sl,
                    "quantity": qty,
                    "unit_size": f"{sl/12:.0f}-FT Commercial Stick",
                    "total_purchased_length": round(tot_len, 1),
                    "total_purchased_weight": round(tot_wt, 1),
                    "notes": f"Standard {sl/12:.0f}' mill length. Saw kerf allowance: {saw_kerf}\"."
                })

    # Plate items grouped by thickness and grade
    plate_groups: Dict[Tuple[float, str], Dict[str, Any]] = {}
    for p in plates:
        mat = _get(p, "material", "")
        if "Expanded Metal" in mat:
            continue
        thk = float(_get(p, "thickness", 0.25))
        grd = _get(p, "grade", "ASTM A36")
        w = float(_get(p, "width", 0.0))
        l = float(_get(p, "length", 0.0))
        qty = int(_get(p, "quantity", 1))
        area = w * l * qty
        key = (thk, grd)
        group = plate_groups.setdefault(key, {"area": 0.0, "parts": []})
        group["area"] += area
        group["parts"].extend([(w, l)] * qty)
        
    plate_sizes = [(24.0, 24.0), (24.0, 48.0), (48.0, 96.0),
                   (48.0, 120.0), (48.0, 144.0)]
    for (thk, grd), group in plate_groups.items():
        net_sq_in = group["area"]
        gross_sq_in = net_sq_in * 1.20   # 20% for shear kerf and drop

        # A purchase blank must fit every individual part, not merely have
        # enough total area. This matters for narrow pieces such as RF1 (3x36),
        # which cannot come out of a 24x24 drop.
        fitting_sizes = [
            (sw, sl) for sw, sl in plate_sizes
            if all((w <= sw and l <= sl) or (w <= sl and l <= sw)
                   for w, l in group["parts"])
        ]
        if not fitting_sizes:
            largest = max(max(w, l) for w, l in group["parts"])
            raise ValueError(
                f"No commercial plate size configured for a {largest:g} in long, "
                f"{thk:g} in thick part."
            )
        sheet_w, sheet_l = fitting_sizes[0]
        sheet_sq_in = sheet_w * sheet_l
        sheets_needed = max(1, math.ceil(gross_sq_in / sheet_sq_in))
        purchased_sq_in = sheets_needed * sheet_sq_in
        purchased_wt = purchased_sq_in * thk * 0.2836
        feet_desc = " (4x8)" if (sheet_w, sheet_l) == (48.0, 96.0) else ""
        unit_desc = (f"{sheet_w:g} x {sheet_l:g} in{feet_desc} x {thk:g} in "
                     "steel plate")

        purchase_rows.append({
            "category": "PLATE",
            "section": f"{thk} in steel plate",
            "grade": grd,
            "stick_length": 0.0,
            "quantity": sheets_needed,
            "unit_size": unit_desc,
            "total_purchased_length": 0.0,
            "total_purchased_weight": round(purchased_wt, 1),
            "notes": f"Buy {sheets_needed} x {unit_desc}. The carrier uses about "
                     f"{net_sq_in / 144.0:.1f} sq ft; weight shown is what you "
                     f"carry out of the steel yard."
        })

    # Grating items
    grating_net_sq_in = 0.0
    for p in plates:
        mat = _get(p, "material", "")
        if "Expanded Metal" in mat:
            w = float(_get(p, "width", 0.0))
            l = float(_get(p, "length", 0.0))
            qty = int(_get(p, "quantity", 1))
            grating_net_sq_in += w * l * qty
            
    if grating_net_sq_in > 0:
        grating_gross_sq_ft = (grating_net_sq_in * 1.15) / 144.0
        grating_sheets = max(1, math.ceil(grating_gross_sq_ft / 32.0))
        grating_wt = grating_sheets * 32.0 * 1.80   # full sheets, as purchased
        purchase_rows.append({
            "category": "GRATING",
            "section": "#9 1-1/2 in flattened expanded metal",
            "grade": "ASTM A36 Carbon Steel",
            "stick_length": 0.0,
            "quantity": grating_sheets,
            "unit_size": "48 x 96 in (4x8) sheet",
            "total_purchased_length": 0.0,
            "total_purchased_weight": round(grating_wt, 1),
            "notes": f"Buy {grating_sheets} full 4x8 sheet(s). The carrier uses "
                     f"about {grating_net_sq_in / 144.0:.1f} sq ft."
        })

    # Bought-out hardware comes from the current carrier assembly. This keeps
    # procurement synchronized with the physical pieces that require it.
    for item in hardware:
        qty = int(_get(item, "quantity", 1))
        unit_wt = float(_get(item, "unit_weight", 0.0))
        purchase_rows.append({
            "category": "HARDWARE",
            "section": _get(item, "section", "Bought-out hardware"),
            "grade": _get(item, "grade", ""),
            "stick_length": 0.0,
            "quantity": qty,
            "unit_size": _get(item, "unit_size", "each"),
            "total_purchased_length": 0.0,
            "total_purchased_weight": round(unit_wt * qty, 1),
            "notes": _get(item, "notes", ""),
        })

    total_purchased_wt = sum(r["total_purchased_weight"] for r in purchase_rows)
    total_cut_wt = total_linear_cut_wt
    overall_eff = (total_linear_cut_wt / total_linear_purchased_wt * 100.0) if total_linear_purchased_wt > 0 else 0.0
    
    return {
        "stock_plan": stock_plan,
        "purchase_list": purchase_rows,
        "total_purchased_weight": round(total_purchased_wt, 1),
        "total_cut_weight": round(total_cut_wt, 1),
        "overall_efficiency_pct": round(overall_eff, 1)
    }
