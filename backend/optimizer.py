from typing import List, Dict, Any
from models import CutListRow, PurchaseRow, StockStick, StockPlanResult
from geometry import MATERIAL_LIBRARY

def optimize_stock(
    cut_list: List[Dict[str, Any]],
    stock_lengths: List[float] = [240.0, 288.0], # 20 ft and 24 ft
    saw_kerf: float = 0.125
) -> Dict[str, Any]:
    """
    1D Cutting Stock Optimizer for Linear Sections.
    Groups items by exact material section, preserving full section identity and grade.
    Packs cuts into optimal stock lengths (20-ft / 24-ft) accounting for saw kerf.
    """
    # Exclude plate and grating profiles from linear bar nesting
    linear_items = [
        item for item in cut_list
        if not item.get("cut_type", "").startswith("PLATE")
        and "Plate" not in item.get("section", "")
        and "Expanded Metal" not in item.get("section", "")
    ]
    
    # Group items by exact section name
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for item in linear_items:
        section = item["section"]
        if section not in grouped:
            grouped[section] = []
        qty = item.get("quantity", 1)
        for _ in range(qty):
            grouped[section].append({
                "piece_mark": item["piece_mark"],
                "length": float(item["cut_length"]),
                "notes": item.get("notes", "")
            })
            
    # Sort available stock lengths ascending (e.g. 240, 288)
    sorted_stock_opts = sorted(stock_lengths)
    if not sorted_stock_opts:
        sorted_stock_opts = [240.0]
        
    stock_plan: List[Dict[str, Any]] = []
    purchase_summary: Dict[str, Dict[float, int]] = {}
    total_purchased_wt = 0.0
    total_cut_wt = 0.0
    
    global_stick_counter = 1
    
    for section, parts in grouped.items():
        if not parts:
            continue
            
        mat_info = MATERIAL_LIBRARY.get(section, {})
        wt_ft = mat_info.get("wt_per_ft", 4.0)
        grade = mat_info.get("grade", "ASTM A500 Gr B")
        
        # Sort parts descending by length (First-Fit Decreasing heuristic)
        parts_remaining = sorted(parts, key=lambda p: p["length"], reverse=True)
        
        if section not in purchase_summary:
            purchase_summary[section] = {sl: 0 for sl in sorted_stock_opts}
            
        while parts_remaining:
            # Determine which stock length to use
            # Try packing into each available stock length and select the one with highest fill ratio
            best_choice = None
            best_waste = float("inf")
            best_packed = []
            best_remaining = []
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
                    # Prefer smaller waste, or if waste is similar, prefer smaller stock length
                    if waste < best_waste or (abs(waste - best_waste) < 1.0 and candidate_sl < best_stock_len):
                        best_waste = waste
                        best_packed = temp_packed
                        best_remaining = temp_rem
                        best_stock_len = candidate_sl
                        
            # If no part fit on any stock length, take the largest and cut what we can or alert
            if not best_packed:
                p = parts_remaining.pop(0)
                best_stock_len = sorted_stock_opts[-1]
                best_packed = [p]
                best_remaining = parts_remaining
                best_waste = max(0.0, best_stock_len - p["length"])
                
            parts_remaining = best_remaining
            purchase_summary[section][best_stock_len] += 1
            
            # Calculate stick metrics
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
            
            # Accumulate weights
            total_purchased_wt += (best_stock_len / 12.0) * wt_ft
            total_cut_wt += (part_sum / 12.0) * wt_ft
            
    # Build clean purchase rows
    purchase_rows: List[Dict[str, Any]] = []
    for section, sl_dict in purchase_summary.items():
        mat_info = MATERIAL_LIBRARY.get(section, {})
        wt_ft = mat_info.get("wt_per_ft", 4.0)
        grade = mat_info.get("grade", "ASTM A500 Gr B")
        
        for sl, qty in sl_dict.items():
            if qty > 0:
                tot_len = sl * qty
                tot_wt = (tot_len / 12.0) * wt_ft
                purchase_rows.append({
                    "section": section,
                    "grade": grade,
                    "stick_length": sl,
                    "quantity": qty,
                    "total_purchased_length": round(tot_len, 1),
                    "total_purchased_weight": round(tot_wt, 1)
                })
                
    overall_eff = (total_cut_wt / total_purchased_wt * 100.0) if total_purchased_wt > 0 else 0.0
    
    return {
        "stock_plan": stock_plan,
        "purchase_list": purchase_rows,
        "total_purchased_weight": round(total_purchased_wt, 1),
        "total_cut_weight": round(total_cut_wt, 1),
        "overall_efficiency_pct": round(overall_eff, 1)
    }
