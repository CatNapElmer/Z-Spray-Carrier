from typing import List, Dict
from models import CutListRow

def optimize_stock(cut_list: List[Dict], stock_lengths: List[float], saw_kerf: float = 0.125) -> Dict:
    # cut_list: list of dicts with "mark", "raw_section", "cut_length", "quantity"
    # Group by raw_section
    grouped = {}
    for item in cut_list:
        section = item["raw_section"]
        if section not in grouped:
            grouped[section] = []
        for _ in range(item["quantity"]):
            grouped[section].append({"mark": item["mark"], "length": item["cut_length"]})
            
    # Default to 20ft (240 inches) if no stock lengths provided
    default_stock = 240.0
    if stock_lengths:
        default_stock = max(stock_lengths)
        
    results = []
    purchase_list = {}
    
    for section, parts in grouped.items():
        # Sort parts descending
        parts.sort(key=lambda x: x["length"], reverse=True)
        sticks = []
        
        for part in parts:
            placed = False
            for stick in sticks:
                if stick["remaining"] >= part["length"] + saw_kerf:
                    stick["parts"].append(part)
                    stick["remaining"] -= (part["length"] + saw_kerf)
                    placed = True
                    break
            if not placed:
                sticks.append({
                    "stock_length": default_stock,
                    "remaining": default_stock - part["length"],
                    "parts": [part]
                })
        
        results.append({
            "section": section,
            "sticks": sticks
        })
        purchase_list[section] = len(sticks)
        
    return {
        "stock_plan": results,
        "purchase_list": [{"section": k, "stick_length": default_stock, "quantity": v} for k, v in purchase_list.items()]
    }

