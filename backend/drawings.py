import os
import math
from typing import List, Dict, Any, Tuple, Optional
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.lib import colors
from models import ProjectParameters, StatusEnum

def fraction_str(val: float, precision: int = 16) -> str:
    """Converts a float into standard structural steel fraction notation (to nearest 1/16\")."""
    if abs(val) < 1e-6:
        return '0"'
    is_neg = val < 0
    abs_val = abs(val)
    units = round(abs_val * precision)
    whole = units // precision
    rem = units % precision
    if rem == 0:
        res = f'{whole}"'
    else:
        gcd = math.gcd(rem, precision)
        num = rem // gcd
        den = precision // gcd
        if whole > 0:
            res = f'{whole} {num}/{den}"'
        else:
            res = f'{num}/{den}"'
    return f"-{res}" if is_neg else res

class DraftingCanvas:
    def __init__(self, c: canvas.Canvas):
        self.c = c
        self.dimension_size = 6.0
        self.width, self.height = landscape(letter) # 792 x 612 pt
        
    def draw_border_and_title_block(
        self,
        sheet_code: str,
        title: str,
        sheet_num: int,
        total_sheets: int = 9,
        scale: str = "NTS"
    ):
        c = self.c
        margin = 36.0 # 0.5 inch margin
        w = self.width
        h = self.height
        
        # Outer Border
        c.setLineWidth(1.5)
        c.setStrokeColor(colors.black)
        c.rect(margin, margin, w - 2 * margin, h - 2 * margin)
        
        # Inner thin border (Drafting standard)
        c.setLineWidth(0.5)
        c.rect(margin + 4, margin + 4, w - 2 * margin - 8, h - 2 * margin - 8)
        
        # Title Block: Bottom Right Corner
        tb_w = 270.0 # 3.75 inches
        tb_h = 82.0  # 1.14 inches
        tb_x = w - margin - 4 - tb_w
        tb_y = margin + 4
        
        c.setLineWidth(1.0)
        c.setFillColor(colors.HexColor("#F8F9FA"))
        c.rect(tb_x, tb_y, tb_w, tb_h, fill=1, stroke=1)
        
        # Title block dividing lines
        c.line(tb_x, tb_y + 54, tb_x + tb_w, tb_y + 54)
        c.line(tb_x, tb_y + 26, tb_x + tb_w, tb_y + 26)
        c.line(tb_x + 160, tb_y, tb_x + 160, tb_y + 54)
        c.line(tb_x + 215, tb_y, tb_x + 215, tb_y + 26)
        
        # Project Title
        c.setFillColor(colors.HexColor("#0D1B2A"))
        c.setFont("Helvetica-Bold", 9.5)
        c.drawString(tb_x + 8, tb_y + 68, "PROJECT: 2026 Z-SPRAY CARRIER")
        c.setFont("Helvetica", 6.5)
        c.drawString(tb_x + 8, tb_y + 58, "MOUNT: 2015 FORD F-350 FLATBED TWIN RECEIVER")
        
        # Drawing Title (Auto-fit so it never overflows box)
        title_up = title.upper()
        t_size = 9.0
        while t_size > 6.5 and c.stringWidth(title_up, "Helvetica-Bold", t_size) > (tb_w - 20):
            t_size -= 0.5
        c.setFont("Helvetica-Bold", t_size)
        c.setFillColor(colors.HexColor("#003566"))
        c.drawString(tb_x + 8, tb_y + 38, title_up)
        c.setFont("Helvetica", 6.5)
        c.setFillColor(colors.black)
        c.drawString(tb_x + 8, tb_y + 30, "SHOP FABRICATION DRAWING (PARAMETRIC)")
        
        # Metadata fields
        c.setFont("Helvetica", 6)
        c.drawString(tb_x + 8, tb_y + 17, "UNITS: INCHES (USCS)")
        c.drawString(tb_x + 8, tb_y + 8, f"SCALE: {scale}")
        
        c.drawString(tb_x + 85, tb_y + 17, "REV: 0")
        c.drawString(tb_x + 85, tb_y + 8, "Z-SPRAY CARRIER")
        
        c.setFont("Helvetica", 6)
        c.drawString(tb_x + 165, tb_y + 17, "SHEET NUMBER")
        c.setFont("Helvetica-Bold", 14)
        c.setFillColor(colors.HexColor("#B7094C"))
        c.drawString(tb_x + 170, tb_y + 5, sheet_code)
        
        c.setFont("Helvetica", 6)
        c.setFillColor(colors.black)
        c.drawString(tb_x + 220, tb_y + 17, "SHEET OF")
        c.setFont("Helvetica-Bold", 11)
        c.drawString(tb_x + 225, tb_y + 6, f"{sheet_num} OF {total_sheets}")
        
        # Quality & Safety Warning Tag at top
        c.setFillColor(colors.HexColor("#D90429"))
        c.rect(margin + 4, h - margin - 16, w - 2 * margin - 8, 12, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 6.5)
        c.drawString(
            margin + 12, h - margin - 12,
            "ALL DIMENSIONS IN INCHES AND GOVERN OVER THE DRAWING.  TACK FIRST - TEST FIT BEFORE FINAL WELD.  "
            "ITEMS MARKED FIELD FIT ARE SET ON THE TRUCK, NOT OFF THIS SHEET."
        )

    def draw_note_box(self, x: float, y: float, w: float, h: float, text: str,
                      heading: str = "READ THIS FIRST"):
        """
        Plain note box. Grows its own height to fit the text so nothing is ever
        clipped, and wraps long lines instead of running off the edge.
        """
        c = self.c
        size = 6.0
        lead = 8.0
        wrapped: List[str] = []
        for raw in text.split(chr(10)):
            line = raw.rstrip()
            if not line:
                wrapped.append("")
                continue
            while c.stringWidth(line, "Helvetica", size) > (w - 14):
                cut = len(line)
                while cut > 1 and c.stringWidth(line[:cut], "Helvetica", size) > (w - 14):
                    cut -= 1
                brk = line.rfind(" ", 0, cut)
                brk = brk if brk > 10 else cut
                wrapped.append(line[:brk])
                line = "   " + line[brk:].lstrip()
            wrapped.append(line)

        need = 16 + len(wrapped) * lead + 6
        h = max(h, need)

        c.setFillColor(colors.HexColor("#FFF3CD"))
        c.setStrokeColor(colors.HexColor("#FFC107"))
        c.setLineWidth(1.0)
        c.rect(x, y, w, h, fill=1, stroke=1)
        c.setFillColor(colors.HexColor("#856404"))
        c.setFont("Helvetica-Bold", 6.5)
        c.drawString(x + 6, y + h - 11, heading.upper())
        c.setFont("Helvetica", size)
        line_y = y + h - 21
        for line in wrapped:
            c.drawString(x + 6, line_y, line)
            line_y -= lead
        return h

    # Kept so existing callers keep working.
    def draw_unverified_banner(self, x: float, y: float, w: float, h: float,
                               text: str, heading: str = "READ THIS FIRST"):
        return self.draw_note_box(x, y, w, h, text, heading)

    def draw_dim_h(self, x1: float, x2: float, y: float, text: str, leader_y: Optional[float] = None, ext_down: bool = True):
        c = self.c
        c.setStrokeColor(colors.HexColor("#333333"))
        c.setLineWidth(0.6)
        
        # Extension lines
        if leader_y is not None:
            c.line(x1, min(y, leader_y) - 2, x1, max(y, leader_y) + 2)
            c.line(x2, min(y, leader_y) - 2, x2, max(y, leader_y) + 2)
        else:
            c.line(x1, y - 5, x1, y + 5)
            c.line(x2, y - 5, x2, y + 5)
            
        # Dimension line
        c.line(x1, y, x2, y)
        
        # Architectural ticks (45-degree slashes)
        tick = 2.5
        c.line(x1 - tick, y - tick, x1 + tick, y + tick)
        c.line(x2 - tick, y - tick, x2 + tick, y + tick)
        
        # Text
        c.setFont("Helvetica-Bold", self.dimension_size)
        c.setFillColor(colors.HexColor("#001219"))
        tw = c.stringWidth(text, "Helvetica-Bold", self.dimension_size)
        mid_x = (x1 + x2) / 2.0
        # White background box for text clarity
        c.setFillColor(colors.white)
        c.rect(mid_x - tw/2 - 2, y - 3, tw + 4, self.dimension_size + 1, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#001219"))
        c.drawCentredString(mid_x, y - 1.5, text)

    def draw_dim_v(self, y1: float, y2: float, x: float, text: str, leader_x: Optional[float] = None):
        c = self.c
        c.setStrokeColor(colors.HexColor("#333333"))
        c.setLineWidth(0.6)
        
        # Extension lines
        if leader_x is not None:
            c.line(min(x, leader_x) - 2, y1, max(x, leader_x) + 2, y1)
            c.line(min(x, leader_x) - 2, y2, max(x, leader_x) + 2, y2)
        else:
            c.line(x - 5, y1, x + 5, y1)
            c.line(x - 5, y2, x + 5, y2)
            
        # Dimension line
        c.line(x, y1, x, y2)
        
        # Architectural ticks
        tick = 2.5
        c.line(x - tick, y1 - tick, x + tick, y1 + tick)
        c.line(x - tick, y2 - tick, x + tick, y2 + tick)
        
        # Text rotated 90 degrees
        c.setFont("Helvetica-Bold", self.dimension_size)
        mid_y = (y1 + y2) / 2.0
        c.saveState()
        c.translate(x, mid_y)
        c.rotate(90)
        tw = c.stringWidth(text, "Helvetica-Bold", self.dimension_size)
        c.setFillColor(colors.white)
        c.rect(-tw/2 - 2, -3.5, tw + 4, self.dimension_size + 1, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#001219"))
        c.drawCentredString(0, -2, text)
        c.restoreState()

    def draw_centerline(self, x1: float, y1: float, x2: float, y2: float):
        c = self.c
        c.setStrokeColor(colors.HexColor("#D90429"))
        c.setLineWidth(0.5)
        c.setDash([10, 3, 2, 3])
        c.line(x1, y1, x2, y2)
        c.setDash([])

    def draw_balloon(self, x: float, y: float, mark: str, leader_to: Optional[Tuple[float, float]] = None):
        c = self.c
        r = max(8.0, self.dimension_size * 1.5 - 1)
        if leader_to:
            c.setStrokeColor(colors.HexColor("#4A4E69"))
            c.setLineWidth(0.6)
            c.line(x, y, leader_to[0], leader_to[1])
            c.setFillColor(colors.HexColor("#4A4E69"))
            c.circle(leader_to[0], leader_to[1], 1.5, fill=1, stroke=0)
            
        c.setFillColor(colors.HexColor("#E0AAFF"))
        c.setStrokeColor(colors.HexColor("#3C096C"))
        c.setLineWidth(1.0)
        c.circle(x, y, r, fill=1, stroke=1)
        c.setFillColor(colors.HexColor("#240046"))
        c.setFont("Helvetica-Bold", self.dimension_size)
        c.drawCentredString(x, y - 2.0, mark)

    def draw_weld_callout(self, x: float, y: float, note: str, leader_to: Tuple[float, float]):
        c = self.c
        c.setStrokeColor(colors.HexColor("#0077B6"))
        c.setLineWidth(0.7)
        c.line(leader_to[0], leader_to[1], x, y)
        c.line(x, y, x + 35, y)
        c.setFillColor(colors.HexColor("#0077B6"))
        c.circle(leader_to[0], leader_to[1], 1.5, fill=1, stroke=1)
        
        c.setFont("Helvetica-Bold", 5.5)
        c.setFillColor(colors.HexColor("#03045E"))
        c.drawString(x + 2, y + 2, note)

    def draw_polygon(self, pts: List[Tuple[float, float]], fill: int = 1, stroke: int = 1):
        c = self.c
        p = c.beginPath()
        if not pts:
            return
        p.moveTo(pts[0][0], pts[0][1])
        for pt in pts[1:]:
            p.lineTo(pt[0], pt[1])
        p.close()
        c.drawPath(p, fill=fill, stroke=stroke)

# -------------------------------------------------------------
# SHEET DRAWING FUNCTIONS
# -------------------------------------------------------------

def draw_sheet_s1(dc: DraftingCanvas, params: ProjectParameters, assembly: Dict[str, Any]):
    """Sheet S1: General Arrangement"""
    dc.draw_border_and_title_block("S1", "GENERAL ARRANGEMENT - PLAN, ELEVATION, & ENVELOPE", 1, 9)
    dc = DraftingCanvas(dc.c)
    dc.dimension_size = 8.0
    c = dc.c
    
    scale = 2.8
    ox = 115.0
    oy = 425.0
    
    # 1. PLAN VIEW
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.HexColor("#001D3D"))
    c.drawString(ox - 30, 540.0, "VIEW A: PLAN - MACHINE CLEARANCES")
    
    # Front Datum Reference Line (X=0)
    c.setStrokeColor(colors.HexColor("#D90429"))
    c.setLineWidth(1.0)
    c.setDash([6, 3])
    c.line(ox, oy - 65, ox, oy + 85)
    c.setDash([])
    c.setFont("Helvetica-Bold", 6.5)
    c.setFillColor(colors.HexColor("#D90429"))
    c.drawString(ox + 6, oy + 62, "FRONT DATUM X=0")
    
    # Twin Receiver Mounts (Stingers S1-L, S1-R)
    # Stinger overlap 20.0" past X=0 (passes under C2 at X=18"), insertion 18.0" forward into truck receivers
    stinger_w = 2.0 * scale
    stinger_span = params.stinger_spacing_model_nominal * scale
    ins_l = params.stinger_insertion_length * scale
    ovl_l = params.stinger_overlap_length * scale
    for y_sign in [-1, 1]:
        sy = oy + y_sign * (stinger_span / 2.0) - (stinger_w / 2.0)
        c.setFillColor(colors.HexColor("#CED4DA"))
        c.setStrokeColor(colors.HexColor("#495057"))
        c.setLineWidth(1.0)
        c.rect(ox - ins_l, sy, ins_l + ovl_l, stinger_w, fill=1, stroke=1)
        # Hitch Pin Hole (3.0" setback)
        hole_x = ox - ins_l + (params.hitch_pin_hole_setback * scale)
        c.setFillColor(colors.HexColor("#D90429"))
        c.circle(hole_x, sy + stinger_w/2, 1.8, fill=1, stroke=1)
        
    # Carrier Deck Outline (36.00" frame width x 63.00" length; 38.00" max across flare tips)
    deck_l = params.carrier_deck_length * scale
    deck_w = params.carrier_width * scale # 36.00"
    
    # Dual Wheel Tracks (11.50" flat width each, 13.00" center gap)
    track_w = params.track_flat_width * scale
    c.setFillColor(colors.HexColor("#E9ECEF"))
    c.setStrokeColor(colors.black)
    c.setLineWidth(1.2)
    c.rect(ox, oy - deck_w/2.0, deck_l, track_w, fill=1, stroke=1)
    c.rect(ox, oy + deck_w/2.0 - track_w, deck_l, track_w, fill=1, stroke=1)
    
    # Open cleanout center gap (13.00" clear)
    c.setFillColor(colors.HexColor("#F8F9FA"))
    c.setStrokeColor(colors.HexColor("#6C757D"))
    c.setLineWidth(0.5)
    c.rect(ox, oy - deck_w/2.0 + track_w, deck_l, deck_w - 2 * track_w, fill=1, stroke=1)
    c.setFont("Helvetica", 6.0)
    c.setFillColor(colors.HexColor("#6C757D"))
    c.drawCentredString(ox + deck_l/2, oy - 2, "OPEN CLEANOUT GAP (13.0\" CLEAR)")
    
    # Flared Guide Outward Projections (1.00" flare per side -> 38.00" MAX outside envelope)
    flare_w = params.flare_width * scale
    c.setStrokeColor(colors.HexColor("#495057"))
    c.setLineWidth(0.8)
    c.line(ox, oy - deck_w/2.0 - flare_w, ox + deck_l, oy - deck_w/2.0 - flare_w)
    c.line(ox, oy + deck_w/2.0 + flare_w, ox + deck_l, oy + deck_w/2.0 + flare_w)
    
    # Machine Envelope Footprint - drawn at the machine's PUBLISHED size.
    # Nothing here is shrunk to make the picture work.
    mach_l = params.machine_length_field * scale
    mach_w = params.machine_width * scale
    mach_front_x = ox + ((params.carrier_deck_length - params.ramp_clearance - params.machine_length_field) * scale)
    overhang = params.machine_length_field - (params.carrier_deck_length - params.ramp_clearance)
    c.setStrokeColor(colors.HexColor("#0077B6"))
    c.setLineWidth(0.8)
    c.setDash([4, 2])
    c.rect(mach_front_x, oy - mach_w/2.0, mach_l, mach_w, fill=0, stroke=1)
    c.setDash([])
    c.setFont("Helvetica-Bold", 6.0)
    c.setFillColor(colors.HexColor("#0077B6"))
    c.drawString(mach_front_x + 6, oy + mach_w/2.0 - 8,
                 f"Z-SPRAY JUNIOR ENVELOPE ({fraction_str(params.machine_length_field)} L x {fraction_str(params.machine_width)} W)")
    c.drawString(mach_front_x + 6, oy + mach_w/2.0 - 15,
                 f"FRONT OVERHANGS THE FRONT OF THE DECK BY {fraction_str(overhang)}")

    # Where the machine's wheels land is settled by rolling it on, so no tyre
    # is drawn here - drawing one would mean inventing a coordinate.
    c.setFont("Helvetica-Bold", 6.0)
    c.setFillColor(colors.HexColor("#D90429"))
    c.drawCentredString(ox + deck_l/2.0, oy - deck_w/2.0 - 26,
                        "CHECK MACHINE CLEARANCE DURING FIT-UP - ROLL THE Z-SPRAY ON AND LOOK")

    # Ramp Hinge Line at X = 63.0"
    hx = ox + deck_l
    dc.draw_centerline(hx, oy - deck_w/2 - 16, hx, oy + deck_w/2 + 16)
    c.setFont("Helvetica-Bold", 6.0)
    c.setFillColor(colors.HexColor("#D90429"))
    c.drawString(hx + 3, oy + deck_w/2 + 8, "RAMP HINGE")
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor("#003566"))
    c.drawCentredString(ox + deck_l/2.0, oy + deck_w/2.0 + 44, "TRUCK SIDE")
    c.drawCentredString(hx + (61.0 * scale)/2.0, oy + deck_w/2.0 + 44, "RAMP SIDE")
    
    # Deployed ramp outline (61.0" length)
    ramp_l = params.ramp_length * scale
    c.setFillColor(colors.HexColor("#E2EAFC"))
    c.setStrokeColor(colors.HexColor("#4361EE"))
    c.setLineWidth(1.0)
    c.setDash([3, 2])
    c.rect(hx, oy - deck_w/2.0, ramp_l, track_w, fill=1, stroke=1)
    c.rect(hx, oy + deck_w/2.0 - track_w, ramp_l, track_w, fill=1, stroke=1)
    c.setDash([])
    c.setFont("Helvetica-Bold", 6.0)
    c.setFillColor(colors.HexColor("#4361EE"))
    c.drawCentredString(hx + ramp_l/2, oy + deck_w/2 - track_w/2 - 2, "DEPLOYED RAMP (61\")")
    
    # Dimensions on Plan View
    dc.draw_dim_h(ox, hx, oy + deck_w/2 + 24, f"CARRIER DECK = {fraction_str(params.carrier_deck_length)}")
    dc.draw_dim_h(hx, hx + ramp_l, oy + deck_w/2 + 24, f"RAMP = {fraction_str(params.ramp_length)}")
    dc.draw_dim_v(oy - deck_w/2 - flare_w, oy + deck_w/2 + flare_w, ox - 54, f"MAX OVERALL = {fraction_str(params.carrier_max_overall_width)} (LIMIT)")
    dc.draw_dim_v(oy - deck_w/2, oy + deck_w/2, ox - 38, f"FRAME WIDTH = {fraction_str(params.carrier_width)}")
    dc.draw_dim_v(oy - deck_w/2, oy - deck_w/2 + track_w, ox - 22, f"TRACK = {fraction_str(params.track_flat_width)}")
    c.setFont("Helvetica-Bold", 6.5)
    c.setFillColor(colors.HexColor("#D90429"))
    c.drawString(500, 455, "MOUNTING TUBES: FIELD FIT TO TRUCK (S4)")
    
    # 2. SIDE ELEVATION VIEW
    e_oy = 165.0
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(colors.HexColor("#001D3D"))
    c.drawString(ox - 30, e_oy + 82, "VIEW B: GENERAL ARRANGEMENT")
    c.drawString(ox - 30, e_oy + 71, "SIDE ELEVATION & DEPLOYMENT")
    
    # Ground Datum Line
    ground_y = e_oy - (params.deck_height * scale)
    dx = math.sqrt(max(1, params.ramp_length**2 - params.deck_height**2)) * scale
    c.setStrokeColor(colors.HexColor("#6C757D"))
    c.setLineWidth(1.0)
    c.line(ox - 45, ground_y, hx + dx + 15, ground_y)
    c.setFont("Helvetica-Bold", 6.0)
    c.setFillColor(colors.HexColor("#6C757D"))
    c.drawString(ox + 10, ground_y + 4, f"GROUND LEVEL (DECK IS {fraction_str(params.deck_height)} UP)")
    
    # Carrier Frame Tube
    c.setStrokeColor(colors.black)
    c.setLineWidth(1.2)
    c.setFillColor(colors.HexColor("#DEE2E6"))
    c.rect(ox, e_oy - (2.0 * scale), deck_l, 2.0 * scale, fill=1, stroke=1)
    # Flared Guide 3" high
    c.setFillColor(colors.HexColor("#ADB5BD"))
    c.rect(ox, e_oy, deck_l, 3.0 * scale, fill=1, stroke=1)
    
    # Upright Ramp (90 deg) at X = 63.0"
    c.setFillColor(colors.HexColor("#CED4DA"))
    c.rect(hx - (2.0 * scale), e_oy, 2.0 * scale, ramp_l, fill=1, stroke=1)
    c.setFont("Helvetica-Bold", 6.0)
    c.setFillColor(colors.HexColor("#343A40"))
    c.drawString(hx + 4, e_oy + ramp_l - 12, "UPRIGHT POSITION (90°)")
    
    # Machine envelope dashed in elevation: X = -10" to +62", height 48"
    c.setStrokeColor(colors.HexColor("#0077B6"))
    c.setLineWidth(0.8)
    c.setDash([3, 2])
    c.rect(mach_front_x, e_oy, mach_l, params.machine_height * scale * 0.45, fill=0, stroke=1)
    c.setDash([])
    
    # Deployed Ramp Line
    c.setStrokeColor(colors.HexColor("#4361EE"))
    c.setLineWidth(1.2)
    c.line(hx, e_oy, hx + dx, ground_y)
    c.setFont("Helvetica-Bold", 6.0)
    c.setFillColor(colors.HexColor("#4361EE"))
    c.drawString(hx + 35, ground_y + 8, f"DEPLOYED SLOPE = {assembly.get('ramp_angle_deg', 16.2)}°")
    
    # Stingers underframe & truck extension (extends 20.0" past X=0 to C2 at X=18")
    c.setFillColor(colors.HexColor("#6C757D"))
    c.rect(ox - ins_l, e_oy - (4.0 * scale), ins_l + ovl_l, 2.0 * scale, fill=1, stroke=1)
    
    # Elevation Dimensions
    dc.draw_dim_v(ground_y, e_oy, ox - 42, f"DECK = {fraction_str(params.deck_height)}")
    dc.draw_dim_v(e_oy, e_oy + (3.0 * scale), ox - 20, f"GUIDE = {fraction_str(params.flared_guide_height)}")
    dc.draw_dim_v(e_oy, e_oy + ramp_l, hx + 22, f"RAMP HT = {fraction_str(params.ramp_length)}")
    
    # Real results, read off the model - no hard-coded verdicts.
    st = assembly.get("structural", {})
    chk = assembly.get("geometry_check_report")
    shop_panel(c, 55, 45, 415, 65, "FIELD FIT TO TRUCK - TACK FIRST", [
        "Spacing: fit to truck. Pin holes: transfer from truck.",
        "Use existing sockets. Nothing welds or bolts to the truck.",
        "STRENGTH [%s]: yields at %.1f g. FIT-UP [%s]."
        % (st.get("status", "?"), st.get("yields_at_g", 0.0),
           getattr(chk, "overall_status", "?")),
    ], size=8)

def draw_sheet_s2(dc: DraftingCanvas, params: ProjectParameters, assembly: Dict[str, Any]):
    """Sheet S2: Main Carrier Weldment - Plan View with Baseline Datum Dimensions"""
    dc.draw_border_and_title_block("S2", "MAIN CARRIER WELDMENT - PLAN VIEW & FITTER DATUMS", 2, 9)
    c = dc.c
    
    ox = 115.0
    oy = 250.0
    scale = 5.8
    
    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColor(colors.HexColor("#001D3D"))
    c.drawString(ox - 30, 535.0, "MAIN CARRIER WELDMENT - SHOP LAYOUT PLAN (TOP VIEW)")
    
    # Front Reference Datum Line X=0
    c.setStrokeColor(colors.HexColor("#D90429"))
    c.setLineWidth(1.2)
    c.setDash([8, 3])
    c.line(ox, oy - 120, ox, oy + 230)
    c.setDash([])
    c.setFont("Helvetica-Bold", 7.0)
    c.setFillColor(colors.HexColor("#D90429"))
    c.drawString(ox + 6, oy + 235, "FRONT DATUM: X = 0.00\" (TRUCK FACE)")
    
    deck_l = params.carrier_deck_length * scale
    deck_w = params.carrier_width * scale # 36.00"
    m_thk = 2.0 * scale
    
    # Longitudinal Frame Tubes M1-L and M1-R
    c.setFillColor(colors.HexColor("#E9ECEF"))
    c.setStrokeColor(colors.black)
    c.setLineWidth(1.2)
    c.rect(ox, oy - deck_w/2.0, deck_l, m_thk, fill=1, stroke=1)
    c.rect(ox, oy + deck_w/2.0 - m_thk, deck_l, m_thk, fill=1, stroke=1)
    
    # Inner Track Support Angles M2-L, M2-R (Y = +/- 6.50", cleanout opening 13.00")
    m2_y_offset = (params.track_center_gap / 2.0) * scale # 6.50" * scale
    c.setFillColor(colors.HexColor("#DEE2E6"))
    c.rect(ox, oy - m2_y_offset - m_thk, deck_l, m_thk, fill=1, stroke=1)
    c.rect(ox, oy + m2_y_offset, deck_l, m_thk, fill=1, stroke=1)
    
    # Crossmembers C1-C4 (Extracted parametrically from assembly members)
    cm_members = [m for m in assembly.get("members", []) if getattr(m, "assembly", "") == "MAIN_CARRIER" and getattr(m, "piece_mark", "").startswith("C")]
    cm_locs = [(getattr(m, "piece_mark", ""), getattr(m, "start_pt", None).x if getattr(m, "start_pt", None) else 0.0) for m in cm_members]
    if not cm_locs:
        cm_locs = [("C1", 1.00), ("C2", 18.00), ("C3", 38.00), ("C4", 62.00)]
        
    c_span = (params.carrier_width - 4.0) * scale # 32.00"
    c_span_y = oy - deck_w/2.0 + m_thk
    
    for mark, x_loc in cm_locs:
        cx = ox + (x_loc * scale) - (m_thk / 2.0)
        c.setFillColor(colors.HexColor("#CED4DA"))
        c.setStrokeColor(colors.black)
        c.setLineWidth(1.0)
        c.rect(cx, c_span_y, m_thk, c_span, fill=1, stroke=1)
        dc.draw_centerline(cx + m_thk/2, c_span_y - 6, cx + m_thk/2, c_span_y + c_span + 6)
        
    # Front Stop Angles G5 (11.50" flat wheel track chock)
    g5_len = params.track_flat_width * scale
    c.setFillColor(colors.HexColor("#6C757D"))
    c.rect(ox + (2.0 * scale), oy - deck_w/2.0, 1.5 * scale, g5_len, fill=1, stroke=1)
    c.rect(ox + (2.0 * scale), oy + deck_w/2.0 - g5_len, 1.5 * scale, g5_len, fill=1, stroke=1)
    
    # Front Chain Bracket G4
    c.setFillColor(colors.HexColor("#343A40"))
    c.rect(ox, oy - (2.0 * scale), 4.0 * scale, 4.0 * scale, fill=1, stroke=1)
    c.setFillColor(colors.white)
    c.circle(ox + (2.5 * scale), oy, 2.5, fill=1, stroke=1)
    
    # FITTER BASELINE DATUM DIMENSIONS (All from X = 0)
    base_y = oy + deck_w/2.0 + 24.0
    dc.draw_dim_h(ox, ox + (1.00 * scale), base_y, "C1 CL = 1\"", ext_down=True)
    dc.draw_dim_h(ox, ox + (18.00 * scale), base_y + 14.0, "C2 CL = 18\"", ext_down=True)
    dc.draw_dim_h(ox, ox + (38.00 * scale), base_y + 28.0, "C3 CL = 38\"", ext_down=True)
    dc.draw_dim_h(ox, ox + (62.00 * scale), base_y + 42.0, "C4 CL = 62\"", ext_down=True)
    dc.draw_dim_h(ox, ox + deck_l, base_y + 56.0, f"OVERALL DECK = {fraction_str(params.carrier_deck_length)}", ext_down=True)
    
    # Transverse Dimensions on Left
    dc.draw_dim_v(oy - deck_w/2, oy + deck_w/2, ox - 38, f"FRAME WIDTH = {fraction_str(params.carrier_width)} (38\" MAX FLARE)")
    dc.draw_dim_v(oy - deck_w/2 + m_thk, oy + deck_w/2 - m_thk, ox - 24, f"CROSSMEMBER C1-C4 = {fraction_str(params.carrier_width - 4.0)}")
    dc.draw_dim_v(oy - deck_w/2, oy - m2_y_offset, ox - 12, f"TRACK = {fraction_str(params.track_flat_width)}")
    
    # Piece Mark Balloons
    dc.draw_balloon(ox + 70, oy + deck_w/2 + 8, "M1-R", leader_to=(ox + 70, oy + deck_w/2 - m_thk/2))
    dc.draw_balloon(ox + 70, oy - deck_w/2 - 14, "M1-L", leader_to=(ox + 70, oy - deck_w/2 + m_thk/2))
    dc.draw_balloon(ox + 42, oy + 28, "C1", leader_to=(ox + (1.00 * scale), oy + 16))
    dc.draw_balloon(ox + (18.00 * scale) + 10, oy - 20, "C2", leader_to=(ox + (18.00 * scale), oy - 6))
    dc.draw_balloon(ox + (38.00 * scale) + 10, oy - 20, "C3", leader_to=(ox + (38.00 * scale), oy - 6))
    dc.draw_balloon(ox + (62.00 * scale) - 12, oy - 20, "C4", leader_to=(ox + (62.00 * scale), oy - 6))
    dc.draw_balloon(ox + 22, oy + 4, "G4", leader_to=(ox + 6, oy))
    
    # Weld Notes
    dc.draw_weld_callout(ox + 116, oy + 68, "3/16 FILLET ALL AROUND (TYP)", leader_to=(ox + (18.00 * scale), oy + deck_w/2 - m_thk))
    dc.draw_weld_callout(ox + 210, oy - deck_w/2 - 28, "3/16 FILLET BOTH SIDES", leader_to=(ox + (38.00 * scale), oy - deck_w/2 + m_thk))

def draw_sheet_s3(dc: DraftingCanvas, params: ProjectParameters, assembly: Dict[str, Any]):
    """Sheet S3: Main Carrier Weldment - Elevation & Sections"""
    dc.draw_border_and_title_block("S3", "MAIN CARRIER WELDMENT - ELEVATION & SECTIONS", 3, 9)
    dc = DraftingCanvas(dc.c)
    dc.dimension_size = 8.0
    c = dc.c
    
    ox = 228.0
    oy = 430.0
    scale = 7.0
    
    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColor(colors.HexColor("#001D3D"))
    c.drawString(55, 540.0, "MAIN CARRIER WELDMENT - SIDE ELEVATION & SECTION A-A")
    
    # Front Datum
    dc.draw_centerline(ox, oy - 50, ox, oy + 60)
    c.setFont("Helvetica-Bold", 6.5)
    c.setFillColor(colors.HexColor("#D90429"))
    c.drawString(ox - 20, oy + 73, "FRONT DATUM X=0")
    
    deck_l = params.carrier_deck_length * scale
    m_thk = 2.0 * scale
    guide_h = params.flared_guide_height * scale
    
    # Main tube profile
    c.setFillColor(colors.HexColor("#E9ECEF"))
    c.setStrokeColor(colors.black)
    c.setLineWidth(1.2)
    c.rect(ox, oy - m_thk, deck_l, m_thk, fill=1, stroke=1)
    
    # Flared Guide Plate Profile
    c.setFillColor(colors.HexColor("#ADB5BD"))
    c.rect(ox, oy, deck_l, guide_h, fill=1, stroke=1)
    
    # Stingers underframe (overlap = 20.0" extends under C2 at X=18.0")
    stinger_ins = params.stinger_insertion_length * scale
    stinger_ovl = params.stinger_overlap_length * scale
    c.setFillColor(colors.HexColor("#CED4DA"))
    c.rect(ox - stinger_ins, oy - (2 * m_thk), stinger_ins + stinger_ovl, m_thk, fill=1, stroke=1)
    
    # Three under-deck mount beams, seen on end
    c.setFillColor(colors.HexColor("#4361EE"))
    for x0 in params.mount_beam_stations:
        bx = ox + (x0 * scale)
        c.rect(bx, oy - (2 * m_thk), 2.0 * scale, m_thk, fill=1, stroke=1)

    # Hinge Sleeves at Rear
    c.setFillColor(colors.HexColor("#343A40"))
    c.circle(ox + deck_l, oy - m_thk/2, 4.5, fill=1, stroke=1)
    
    # Elevation Dimensions
    dc.draw_dim_v(oy - m_thk, oy, ox - stinger_ins - 15, "2\" FRAME")
    dc.draw_dim_v(oy - 2*m_thk, oy, ox - stinger_ins - 32, "FRAME + MOUNT TUBE")
    dc.draw_dim_v(oy, oy + guide_h, ox + deck_l + 20, f"GUIDE = {fraction_str(params.flared_guide_height)}")
    dc.draw_dim_h(ox - stinger_ins, ox, oy - 2*m_thk - 34, "INTO THE TRUCK SOCKET: FIELD FIT")
    dc.draw_dim_h(ox, ox + stinger_ovl, oy - 2*m_thk - 20,
                  f"MOUNTING TUBE RUNS BACK {fraction_str(params.stinger_overlap_length)}")
    # label the three mount beams that appear in this elevation
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(colors.HexColor("#003566"))
    for i, x0 in enumerate(params.mount_beam_stations, start=1):
        bx = ox + (x0 + 1.0) * scale
        c.drawCentredString(bx, oy - 2*m_thk - 8, f"MB{i}")
    c.setFont("Helvetica-Bold", 11)
    c.drawString(ox - stinger_ins, oy + guide_h + 40, "TRUCK SIDE")
    c.drawRightString(ox + deck_l, oy + guide_h + 40, "RAMP SIDE")
    dc.draw_dim_h(ox, ox + deck_l, oy + guide_h + 16, f"OVERALL DECK = {fraction_str(params.carrier_deck_length)}")
    
    # SECTION A-A (Enlarged Detail)
    sec_x = 210.0
    sec_y = 155.0
    sec_scale = 22.0
    
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(colors.HexColor("#001D3D"))
    c.drawString(sec_x, sec_y + 165, "SECTION A-A: WHEEL TRACK & 1.0\" FORMED 45-DEG FLARED GUIDE")
    
    # Outer Tube M1
    c.setFillColor(colors.HexColor("#DEE2E6"))
    c.setStrokeColor(colors.black)
    c.setLineWidth(1.2)
    c.rect(sec_x, sec_y, 2.0 * sec_scale, 2.0 * sec_scale, fill=1, stroke=1)
    
    # Inner Support Angle M2
    track_span = params.track_flat_width * sec_scale # 11.50" flat width
    c.rect(sec_x + track_span - (2.0 * sec_scale), sec_y, 2.0 * sec_scale, 2.0 * sec_scale, fill=1, stroke=1)
    
    # Grating line
    c.setStrokeColor(colors.HexColor("#495057"))
    c.setLineWidth(1.5)
    c.line(sec_x, sec_y + 2.0 * sec_scale, sec_x + track_span, sec_y + 2.0 * sec_scale)
    
    # Formed Guide (3.0" vertical + 1.0" outward horizontal flare -> total 38.00" max completed width)
    g_start_x = sec_x
    g_start_y = sec_y + 2.0 * sec_scale
    g_vert_y = g_start_y + (3.0 * sec_scale)
    g_flare_x = g_start_x - (1.0 * sec_scale) # 1.00" flare
    g_flare_y = g_vert_y + (1.0 * sec_scale)
    
    c.setStrokeColor(colors.black)
    c.setLineWidth(2.0)
    c.line(g_start_x, g_start_y, g_start_x, g_vert_y)
    c.line(g_start_x, g_vert_y, g_flare_x, g_flare_y)
    
    # Section Dimensions
    dc.draw_dim_h(sec_x, sec_x + track_span, sec_y - 14, f"TRACK FLAT WIDTH = {fraction_str(params.track_flat_width)}")
    dc.draw_dim_v(g_start_y, g_vert_y, sec_x + track_span + 14, "3.0\" VERTICAL")
    dc.draw_dim_h(g_flare_x, g_start_x, g_flare_y + 15, "1.0\" FLARE (38\" MAX OVERALL)")
    
    dc.draw_balloon(sec_x - 25, g_vert_y + 4, "FG1-L", leader_to=(g_start_x, g_vert_y))
    dc.draw_balloon(sec_x - 18, sec_y + 10, "M1-L", leader_to=(sec_x, sec_y + 10))
    dc.draw_balloon(sec_x + track_span + 18, sec_y + 10, "M2-L", leader_to=(sec_x + track_span, sec_y + 10))

def draw_sheet_s4(dc: DraftingCanvas, params: ProjectParameters, assembly: Dict[str, Any]):
    """Sheet S4: how the carrier hangs on the truck. Nothing here is measured."""
    dc.draw_border_and_title_block("S4", "TRUCK MOUNT - FIELD FIT TO TRUCK", 4, 9)
    dc = DraftingCanvas(dc.c)
    dc.dimension_size = 8.0
    c = dc.c

    ox, oy, scale = 260.0, 355.0, 5.0
    spacing = params.stinger_spacing_model_nominal * scale
    tube_w = 2.0 * scale
    sleeve_w = 2.5 * scale
    ins_l = params.stinger_insertion_length * scale
    ovl_l = params.stinger_overlap_length * scale

    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColor(colors.HexColor("#001D3D"))
    c.drawString(60, 545.0, "TRUCK MOUNT - PLAN LOOKING DOWN")
    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColor(colors.HexColor("#D90429"))
    c.drawString(60, 532.0,
                 "THE TRUCK SETS THE SPACING. THERE IS NO SPACING DIMENSION ON THIS SHEET.")

    # Deck side rails, so it is obvious where the tubes sit relative to them
    rail_y = (params.carrier_width / 2.0) * scale
    c.setStrokeColor(colors.HexColor("#ADB5BD"))
    c.setLineWidth(0.7)
    for sgn in (-1, 1):
        yy = oy + sgn * rail_y
        c.line(ox, yy, ox + params.carrier_deck_length * scale, yy)
    c.setFont("Helvetica", 5.5)
    c.setFillColor(colors.HexColor("#6C757D"))
    c.drawString(ox + 6, oy + rail_y + 4, "OUTSIDE OF DECK SIDE RAIL M1-R")
    c.drawString(ox + 6, oy - rail_y - 10, "OUTSIDE OF DECK SIDE RAIL M1-L")

    # Front face of the deck
    dc.draw_centerline(ox, oy - spacing / 2 - 44, ox, oy + spacing / 2 + 34)
    c.setFont("Helvetica-Bold", 6.5)
    c.setFillColor(colors.HexColor("#D90429"))
    c.drawCentredString(ox + 4, oy + spacing / 2 + 40, "TRUCK SIDE - FRONT FACE OF DECK (X = 0)")

    # Three under-deck mount beams
    c.setStrokeColor(colors.HexColor("#0D1B2A"))
    c.setLineWidth(1.2)
    for i, x0 in enumerate(params.mount_beam_stations, start=1):
        bx = ox + x0 * scale
        c.setFillColor(colors.HexColor("#A2C4F4"))
        c.rect(bx, oy - spacing / 2 + sleeve_w / 2, 2.0 * scale,
               spacing - sleeve_w, fill=1, stroke=1)
        dc.draw_balloon(bx + scale, oy + spacing / 2 - 26 - ((i - 1) % 2) * 20,
                        f"MB{i}",
                        leader_to=(bx + scale, oy + spacing / 2 - sleeve_w / 2))

    # The two mounting tubes with their slip-on sleeves
    for sgn, side in ((-1, "L"), (1, "R")):
        sy = oy + sgn * (spacing / 2.0)
        c.setFillColor(colors.HexColor("#CED4DA"))
        c.setStrokeColor(colors.black)
        c.setLineWidth(1.2)
        c.rect(ox - ins_l, sy - tube_w / 2, ins_l + ovl_l, tube_w, fill=1, stroke=1)
        c.setFillColor(colors.HexColor("#8D99AE"))
        c.rect(ox + 0.5 * scale, sy - sleeve_w / 2,
               params.stinger_sleeve_length * scale, sleeve_w, fill=1, stroke=1)
        dc.draw_centerline(ox - ins_l - 12, sy, ox + ovl_l + 14, sy)
        c.setFillColor(colors.HexColor("#D90429"))
        c.circle(ox - ins_l + params.hitch_pin_hole_setback * scale, sy, 2.5,
                 fill=1, stroke=1)
        dc.draw_balloon(ox + ovl_l + 40, sy, f"S1-{side}",
                        leader_to=(ox + ovl_l - 6, sy))
        dc.draw_balloon(ox + 30 * scale, sy - sgn * 24, f"SL-{side}",
                        leader_to=(ox + 30 * scale, sy - sgn * sleeve_w / 2))

    # Callouts where the truck governs - words, not numbers
    c.setFont("Helvetica-Bold", 6.5)
    c.setFillColor(colors.HexColor("#D90429"))
    c.drawCentredString(ox - ins_l / 2, oy + spacing / 2 + 14, "FIELD FIT TO TRUCK")
    c.drawString(55, oy - spacing / 2 - 22,
                 "TRANSFER PIN HOLES FROM TRUCK")
    c.setFillColor(colors.HexColor("#003566"))
    c.drawCentredString(ox + 21 * scale, oy + 4, "CUT MB1 / MB2 / MB3 TO FIT")
    c.setFont("Helvetica", 6.0)
    c.drawCentredString(ox + 21 * scale, oy - 7,
                       "between the two mounting tubes - approx 35\" each")

    # The only dimensions that are genuinely ours to give
    dc.draw_dim_h(ox, ox + ovl_l, oy + spacing / 2 + 56,
                  "MOUNTING TUBE RUNS BACK 40\"")
    for i, x0 in enumerate(params.mount_beam_stations, start=1):
        dc.draw_dim_h(ox, ox + (x0 + 1.0) * scale,
                      oy - spacing / 2 - 4 - i * 17,
                      f"MB{i} CENTRE = {fraction_str(x0 + 1.0)} FROM TRUCK SIDE")

    shop_panel(c, 55, 48, 415, 147, "FIELD FIT TO TRUCK - IN THIS ORDER", [
        "1. SLIDE both stingers into the truck sockets.",
        "2. PIN / LOCATE them. The truck sets the spacing.",
        "3. SQUARE, level and clamp the carrier. Slip sleeves",
        "   against the socket faces.",
        "4. CUT MB1 / MB2 / MB3 TO FIT between the tubes.",
        "5. TACK ONLY - beams and sleeves.",
        "6. REMOVE carrier: pull pins and lift off the truck.",
        "7. FINISH WELD on the ground.",
        "No truck modifications. Nothing welded or bolted to truck.",
    ], size=8.5)


def draw_sheet_s5(dc: DraftingCanvas, params: ProjectParameters, assembly: Dict[str, Any]):
    """Sheet S5: Ramp Weldment - Plan View"""
    dc.draw_border_and_title_block("S5", "RAMP WELDMENT - PLAN VIEW & CROSSMEMBER LOCATIONS", 5, 9)
    c = dc.c
    
    ox = 115.0
    oy = 250.0
    scale = 5.8
    
    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColor(colors.HexColor("#001D3D"))
    c.drawString(ox - 30, 535.0, "RAMP WELDMENT - PLAN LAYOUT (ONE RIGID ASSEMBLY)")
    
    # Hinge Datum Line
    dc.draw_centerline(ox, oy - 120, ox, oy + 230)
    c.setFont("Helvetica-Bold", 7.0)
    c.setFillColor(colors.HexColor("#D90429"))
    c.drawString(ox + 6, oy + 235, "HINGE DATUM (X = 0.0\" RAMP / X = 63.0\" CARRIER)")
    
    ramp_l = params.ramp_length * scale
    deck_w = params.carrier_width * scale # 36.00"
    m_thk = 2.0 * scale
    
    # Outer Side Tubes R1-L and R1-R
    c.setFillColor(colors.HexColor("#E9ECEF"))
    c.setStrokeColor(colors.black)
    c.setLineWidth(1.2)
    c.rect(ox, oy - deck_w/2.0, ramp_l, m_thk, fill=1, stroke=1)
    c.rect(ox, oy + deck_w/2.0 - m_thk, ramp_l, m_thk, fill=1, stroke=1)
    
    # Inner Support Rails R2-L and R2-R (Y = +/- 6.50", cleanout gap 13.00")
    m2_y_offset = (params.track_center_gap / 2.0) * scale
    c.setFillColor(colors.HexColor("#DEE2E6"))
    c.rect(ox, oy - m2_y_offset - m_thk, ramp_l, m_thk, fill=1, stroke=1)
    c.rect(ox, oy + m2_y_offset, ramp_l, m_thk, fill=1, stroke=1)
    
    # Ramp Crossmembers RC1 to RC5 (32.00" span between side tubes)
    rc_locs = [
        ("RC1", 0.50, "RC1"),
        ("RC2", 15.00, "RC2"),
        ("RC3", 30.00, "RC3"),
        ("RC4", 45.00, "RC4"),
        ("RC5", 60.00, "RC5")
    ]
    rc_span = (params.carrier_width - 4.0) * scale # 32.00"
    rc_span_y = oy - deck_w/2.0 + m_thk
    
    for mark, dist, desc in rc_locs:
        rx = ox + (dist * scale) - (m_thk / 2.0)
        c.setFillColor(colors.HexColor("#CED4DA"))
        c.setStrokeColor(colors.black)
        c.setLineWidth(1.0)
        c.rect(rx, rc_span_y, m_thk, rc_span, fill=1, stroke=1)
        dc.draw_centerline(rx + m_thk/2, rc_span_y - 6, rx + m_thk/2, rc_span_y + rc_span + 6)
        
    # Beveled Ground Transition Plate RF1
    c.setFillColor(colors.HexColor("#6C757D"))
    c.rect(ox + ramp_l, oy - deck_w/2.0, 3.0 * scale, deck_w, fill=1, stroke=1)
    
    # Baseline Dimensions from Hinge Line
    base_y = oy + deck_w/2.0 + 26.0
    dc.draw_dim_h(ox, ox + (15.00 * scale), base_y, "RC2 = 15\"", ext_down=True)
    dc.draw_dim_h(ox, ox + (30.00 * scale), base_y + 14.0, "RC3 = 30\"", ext_down=True)
    dc.draw_dim_h(ox, ox + (45.00 * scale), base_y + 28.0, "RC4 = 45\"", ext_down=True)
    dc.draw_dim_h(ox, ox + (60.00 * scale), base_y + 42.0, "RC5 = 60\"", ext_down=True)
    dc.draw_dim_h(ox, ox + ramp_l, base_y + 56.0, f"TOTAL RAMP = {fraction_str(params.ramp_length)}", ext_down=True)
    
    # Transverse Dims
    dc.draw_dim_v(oy - deck_w/2, oy + deck_w/2, ox - 35, f"FRAME WIDTH = {fraction_str(params.carrier_width)}")
    dc.draw_dim_v(oy - deck_w/2, oy - m2_y_offset, ox - 18, f"TRACK = {fraction_str(params.track_flat_width)}")
    
    # Balloons
    dc.draw_balloon(ox + 55, oy + deck_w/2 + 8, "R1-R", leader_to=(ox + 55, oy + deck_w/2 - m_thk/2))
    dc.draw_balloon(ox + 55, oy - deck_w/2 - 14, "R1-L", leader_to=(ox + 55, oy - deck_w/2 + m_thk/2))
    dc.draw_balloon(ox + (30.00 * scale) + 10, oy - 18, "RC3", leader_to=(ox + (30.00 * scale), oy))
    dc.draw_balloon(ox + ramp_l + 10, oy, "RF1", leader_to=(ox + ramp_l, oy))

def draw_sheet_s6(dc: DraftingCanvas, params: ProjectParameters, assembly: Dict[str, Any]):
    """Sheet S6: Ramp Weldment - Elevation & Hinge Detail"""
    dc.draw_border_and_title_block("S6", "RAMP ELEVATION, DEPLOYMENT ANGLE, & HINGE DETAIL", 6, 9)
    dc = DraftingCanvas(dc.c)
    dc.dimension_size = 8.0
    c = dc.c
    
    scale = 4.2
    ox = 120.0
    oy = 255.0
    
    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColor(colors.HexColor("#001D3D"))
    c.drawString(ox - 60, 535.0, f"RAMP: {assembly.get('ramp_angle_deg', 0):.0f} DEG DOWN ON THE GROUND, 90 DEG UPRIGHT FOR TRAVEL")
    
    # Carrier Rear End Stub
    c.setFillColor(colors.HexColor("#DEE2E6"))
    c.setStrokeColor(colors.black)
    c.setLineWidth(1.2)
    c.rect(ox - (15.0 * scale), oy - (2.0 * scale), 15.0 * scale, 2.0 * scale, fill=1, stroke=1)
    
    # Ground Line
    deck_h = params.deck_height * scale
    ground_y = oy - deck_h
    ramp_l = params.ramp_length * scale
    dx = math.sqrt(max(1, ramp_l**2 - deck_h**2))
    c.setStrokeColor(colors.HexColor("#6C757D"))
    c.setLineWidth(1.0)
    c.line(ox - 30, ground_y, ox + dx + 15, ground_y)
    c.setFont("Helvetica-Bold", 6.0)
    c.setFillColor(colors.HexColor("#6C757D"))
    c.drawString(ox + 10, ground_y + 12, f"GROUND LEVEL (DECK IS {fraction_str(params.deck_height)} UP)")
    
    # Deployed Ramp Member
    c.setStrokeColor(colors.black)
    c.setLineWidth(1.5)
    c.line(ox, oy, ox + dx, ground_y)
    c.line(ox, oy - (2.0 * scale), ox + dx, ground_y - (0.5 * scale))
    
    # Upright Transport Ramp (90 deg)
    c.setFillColor(colors.HexColor("#CED4DA"))
    c.rect(ox - (2.0 * scale), oy, 2.0 * scale, ramp_l, fill=1, stroke=1)
    c.setFont("Helvetica-Bold", 6.0)
    c.setFillColor(colors.HexColor("#343A40"))
    c.drawString(ox + 4, oy + ramp_l - 12, "UPRIGHT FOR TRAVEL (90 DEG)")
    
    # Dims
    dc.draw_dim_v(ground_y, oy, ox - 20, f"DECK = {fraction_str(params.deck_height)}")
    dc.draw_dim_v(oy, oy + ramp_l, ox - 20, f"UPRIGHT = {fraction_str(params.ramp_length)}")
    dc.draw_dim_h(ox, ox + dx, ground_y - 16, f"GROUND HORIZ SPAN = {fraction_str(dx/scale)}")
    
    # ENLARGED HINGE DETAIL VIEW (Cleanly positioned in open upper-right quadrant)
    det_x = 546.0
    det_y = 422.0
    det_scale = 43.0

    od = params.hinge_barrel_od
    rr = od / 2.0

    c.setFont("Helvetica-Bold", 9.0)
    c.setFillColor(colors.HexColor("#001D3D"))
    c.drawString(det_x - 130, det_y + 90, "DETAIL B: HINGE - LOOKING FROM THE SIDE")
    c.setFont("Helvetica-Bold", 7.0)
    c.setFillColor(colors.HexColor("#D90429"))
    c.drawString(det_x - 130, det_y + 77,
                 f"GAP = ONE BARREL DIAMETER ({fraction_str(od)})")

    # Carrier rear cross tube C4 (deck top sits at det_y)
    c.setFillColor(colors.HexColor("#DEE2E6"))
    c.setStrokeColor(colors.black)
    c.setLineWidth(1.0)
    c.rect(det_x - 2.0 * det_scale, det_y - 2.0 * det_scale,
           2.0 * det_scale, 2.0 * det_scale, fill=1, stroke=1)
    # Ramp head cross tube RC1, one barrel diameter away
    c.rect(det_x + od * det_scale, det_y - 2.0 * det_scale,
           2.0 * det_scale, 2.0 * det_scale, fill=1, stroke=1)
    c.setFont("Helvetica-Bold", 8.0)
    c.setFillColor(colors.HexColor("#343A40"))
    c.drawCentredString(det_x - det_scale, det_y - det_scale - 3, "C4")
    c.drawCentredString(det_x + (od + 1.0) * det_scale, det_y - det_scale - 3, "RC1")
    c.setFont("Helvetica", 6.0)
    c.drawCentredString(det_x - det_scale, det_y - det_scale - 14, "CARRIER")
    c.drawCentredString(det_x + (od + 1.0) * det_scale, det_y - det_scale - 14, "RAMP")

    # Top of frame line
    c.setStrokeColor(colors.HexColor("#4361EE"))
    c.setLineWidth(1.2)
    c.line(det_x - 2.3 * det_scale, det_y, det_x - 1.1 * det_scale, det_y)
    c.line(det_x + (od + 1.1) * det_scale, det_y,
           det_x + (od + 2.3) * det_scale, det_y)
    c.setFont("Helvetica-Bold", 6.0)
    c.setFillColor(colors.HexColor("#4361EE"))
    c.drawString(det_x - 2 * det_scale, det_y + 8, "TOP OF FRAME")

    # Barrel, tangent to the deck top and to the cross tube face
    cx = det_x + rr * det_scale
    cy = det_y + rr * det_scale
    c.setStrokeColor(colors.black)
    c.setFillColor(colors.HexColor("#495057"))
    c.circle(cx, cy, rr * det_scale, fill=1, stroke=1)
    c.setFillColor(colors.white)
    c.circle(cx, cy, (params.hinge_barrel_id / 2.0) * det_scale, fill=1, stroke=1)
    c.setFillColor(colors.HexColor("#D90429"))
    c.circle(cx, cy, (params.hinge_pin_dia / 2.0) * det_scale, fill=1, stroke=1)

    dc.draw_balloon(cx + 78, cy + 46, "P1", leader_to=(cx, cy))
    dc.draw_weld_callout(det_x - 100, det_y + 52, "1/4 FILLET TOP AND BOTTOM",
                         leader_to=(cx + rr * det_scale * 0.7, cy - rr * det_scale * 0.7))
    dc.draw_dim_h(det_x, det_x + od * det_scale, det_y - 2.7 * det_scale,
                  f"GAP = {fraction_str(od)}")

    shop_panel(c, 405, 134, 330, 160, "HINGE FIT-UP - TACK FIRST", [
        f"Cut {params.hinge_barrel_count} barrels {fraction_str(params.hinge_barrel_length)} long; {fraction_str(od)} OD x {fraction_str(params.hinge_barrel_wall)} wall.",
        "1. PUT BARRELS ON PIN.",
        "2. ALTERNATE carrier / ramp. Outer ends: carrier.",
        "3. CLAMP AND TACK. Set one barrel diameter gap;",
        "   bottoms flush with frame tops, backs against faces.",
        "4. SWING RAMP from ground to upright.",
        "5. GRIND leading cross-tube edge if anything rubs.",
        "6. WELD OUT - above and below, full barrel length.",
        f"PIN: {fraction_str(params.hinge_pin_dia)} round x {fraction_str(params.hinge_pin_length)}. Clips 1/2\" from ends.",
        f"BORE: {fraction_str(params.hinge_barrel_id)} - 1/8\" loose on purpose. DO NOT REAM.",
    ], size=8)

def shop_panel(c, x, y, w, h, title, lines, size=8):
    """A bounded shop-note panel; coordinates are page layout only."""
    c.setFillColor(colors.HexColor("#F1F4F7"))
    c.setStrokeColor(colors.HexColor("#A8B4C0"))
    c.setLineWidth(0.6)
    c.rect(x, y, w, h, fill=1, stroke=1)
    c.setFillColor(colors.HexColor("#003566"))
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x + 10, y + h - 17, title)
    c.setFillColor(colors.black)
    c.setFont("Helvetica", size)
    for i, line in enumerate(lines):
        c.drawString(x + 10, y + h - 34 - i * (size + 3), line)


def draw_sheet_s7(dc: DraftingCanvas, params: ProjectParameters, assembly: Dict[str, Any]):
    """Five large, grouped details. All dimensions and marks are unchanged."""
    dc.draw_border_and_title_block("S7", "SMALL PARTS - CUT AND FIT", 7, 9)
    dc = DraftingCanvas(dc.c)
    dc.dimension_size = 9
    c = dc.c
    c.setFillColor(colors.HexColor("#001D3D"))
    c.setFont("Helvetica-Bold", 13)
    c.drawString(55, 536, "SMALL PARTS - WHAT TO CUT AND DRILL")
    # Three full-width columns; notes sit below, never inside the part outline.
    for x in (55, 285, 515):
        c.setStrokeColor(colors.HexColor("#CED4DA"))
        c.setLineWidth(0.6)
        c.rect(x, 294, 220, 224)
    for x in (55, 285):
        c.rect(x, 133, 220, 149)

    def text(x, y, value, size=8, bold=False):
        c.setFillColor(colors.HexColor("#003566") if bold else colors.black)
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawString(x, y, value)

    def part_rect(x, y, w, h):
        c.setFillColor(colors.HexColor("#DEE2E6"))
        c.setStrokeColor(colors.black)
        c.setLineWidth(1.2)
        c.rect(x, y, w, h, fill=1, stroke=1)

    text(65, 496, "MB1 / MB2 / MB3", 13, True)
    text(65, 480, f"{params.mount_beam_section} - QTY 3")
    text(65, 466, 'CUT TO FIT - APPROX 35" EACH', 9, True)
    part_rect(73, 412, 172, 25)
    dc.draw_dim_h(73, 245, 394, "CUT TO FIT")
    for i, line in enumerate([
        "CUT WITH CARRIER ON THE TRUCK.",
        "Fit between the two mounting tubes.",
        "Square ends. Weld all round to sleeves",
        "and up to rails where they cross.",
        "No gussets.",
    ]):
        text(65, 369 - i * 13, line, 8, i == 0)

    text(295, 496, "G2-L / G2-R", 13, True)
    text(295, 480, 'LIGHT GUARDS - QTY 2 - 3/16" A36')
    part_rect(334, 374, 120, 90)
    # Opening retains the original 6.75 x 2.5 proportions.
    c.setFillColor(colors.white)
    c.roundRect(343.375, 400.25, 101.25, 37.5, 14, fill=1, stroke=1)
    dc.draw_dim_h(334, 454, 359, '8.0" WIDTH')
    dc.draw_dim_v(374, 464, 318, '6.0" HEIGHT')
    text(295, 347, '6 3/4" x 2 1/2" OVAL', 10, True)
    text(295, 331, 'FOR A 6" LED LAMP')

    text(525, 496, f"HS1 - HS{params.hinge_barrel_count}", 13, True)
    text(525, 480, f"HINGE BARRELS - QTY {params.hinge_barrel_count}")
    text(525, 464, f"{fraction_str(params.hinge_barrel_od)} OD x {fraction_str(params.hinge_barrel_wall)} WALL DOM")
    text(525, 450, f"{fraction_str(params.hinge_barrel_id)} BORE")
    bl = params.hinge_barrel_length * 34
    bd = params.hinge_barrel_od * 34
    part_rect(549, 391, bl, bd)
    c.setFillColor(colors.white)
    c.rect(549, 391 + bd * .3, bl, bd * .4, fill=1, stroke=1)
    dc.draw_dim_h(549, 549 + bl, 375, fraction_str(params.hinge_barrel_length))
    text(525, 347, "NO EARS. NO TABS. NO MACHINING.", 8, True)
    text(525, 331, "Slide barrels on pin, then tack.")
    text(525, 315, "CHECK RAMP SWING BEFORE FINAL WELD", 8, True)

    text(65, 262, "G4 - CHAIN TIE-DOWN", 11, True)
    text(65, 247, 'QTY 1 - 3/8" A36 - 1.00" HOLE')
    part_rect(129, 158, 56, 70)
    c.setFillColor(colors.white)
    c.circle(157, 193, 7, fill=1, stroke=1)
    dc.draw_dim_h(129, 185, 143, '4.0" W')
    dc.draw_dim_v(158, 228, 108, '5.0" H')

    text(295, 262, "G5-L / G5-R - WHEEL STOPS", 11, True)
    text(295, 247, "QTY 2 - L 2x2x1/4 A36")
    part_rect(311, 180, 172.5, 30)
    dc.draw_dim_h(311, 483.5, 160, '11.50" CUT')


def _fit(c, text: str, width: float, font: str = "Helvetica",
         size: float = 6.0) -> str:
    """Trim text to the column width, with an ellipsis so nothing looks complete
    when it is not."""
    text = text or ""
    if c.stringWidth(text, font, size) <= width:
        return text
    while text and c.stringWidth(text + "...", font, size) > width:
        text = text[:-1]
    return text + "..."


def draw_sheet_s8(dc: DraftingCanvas, params: ProjectParameters, assembly: Dict[str, Any]):
    """Sheet S8: every piece in the carrier. Nothing is allowed to fall off."""
    dc.draw_border_and_title_block("S8", "BILL OF MATERIALS & FABRICATION SCHEDULE", 8, 9)
    c = dc.c

    ox = 55.0
    oy = 528.0
    bom = assembly.get("bom", [])

    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColor(colors.HexColor("#001D3D"))
    c.drawString(ox, oy, f"BILL OF MATERIALS - ALL {len(bom)} PIECES")
    c.setFont("Helvetica-Bold", 6.5)
    c.setFillColor(colors.HexColor("#D90429"))
    c.drawString(ox + 250, oy,
                 "CUT TO FIT = do not cut to the length shown; fit it on the job.")

    # Keep only the information a fabricator needs at the saw and bench.
    # Assembly, grade, and weight remain available in the CSV package.
    # Two narrow schedule columns keep every piece on one Letter sheet without
    # forcing the saw-side text down to unreadable type.
    cols = [("MARK", 34), ("SHOP ITEM", 96), ("MATERIAL", 79),
            ("CUT", 40), ("QTY", 22), ("NOTE", 69)]
    table_w = sum(w for _n, w in cols) + 8
    column_x = (38.0, 410.0)
    rows_per_column = math.ceil(len(bom) / 2)
    row_h = 10.5

    def draw_schedule_column(x: float, rows: List[Dict[str, Any]], shade_offset: int):
        y = oy - 16
        c.setFillColor(colors.HexColor("#003566"))
        c.rect(x, y - 4, table_w, 14, fill=1, stroke=0)
        cur_x = x + 4
        c.setFont("Helvetica-Bold", 6.4)
        c.setFillColor(colors.white)
        for name, w in cols:
            c.drawString(cur_x, y, name)
            cur_x += w

        y -= 11
        for i, row in enumerate(rows):
            c.setFillColor(colors.HexColor("#F1F3F5") if (i + shade_offset) % 2 == 0 else colors.white)
            c.rect(x, y - 2.4, table_w, row_h, fill=1, stroke=0)
            field_fit = bool(row.get("field_fit"))
            cur_x = x + 4
            c.setFillColor(colors.HexColor("#B7094C") if field_fit else colors.black)
            c.setFont("Helvetica-Bold", 6.3)
            c.drawString(cur_x, y, row.get("piece_mark", ""))
            cur_x += cols[0][1]
            c.setFillColor(colors.black)
            c.setFont("Helvetica", 6.3)
            for value, (_name, width) in zip(
                    [row.get("description", "").split(" - ", 1)[0],
                     row.get("size", ""),
                     fraction_str(row.get("cut_length", 0.0)),
                     str(row.get("quantity", 1))], cols[1:5]):
                c.drawString(cur_x, y, _fit(c, value, width - 4, "Helvetica", 6.3))
                cur_x += width
            note = row.get("notes", "")
            if field_fit:
                note = "CUT TO FIT"
                c.setFillColor(colors.HexColor("#B7094C"))
                c.setFont("Helvetica-Bold", 6.3)
            c.drawString(cur_x, y, _fit(c, note, cols[5][1] - 4, "Helvetica", 6.3))
            y -= row_h

    draw_schedule_column(column_x[0], bom[:rows_per_column], 0)
    draw_schedule_column(column_x[1], bom[rows_per_column:], rows_per_column)

    # Summary box, clear of both the table and the title block.
    box_h = 54.0
    c.setFillColor(colors.HexColor("#FFF3CD"))
    c.setStrokeColor(colors.HexColor("#856404"))
    c.setLineWidth(1.0)
    c.rect(ox, 48.0, 410.0, box_h, fill=1, stroke=1)

    st = assembly.get("structural", {})
    c.setFillColor(colors.HexColor("#D90429"))
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(ox + 8, 48.0 + box_h - 14,
                 f"STRENGTH CHECK [{st.get('status', '?')}] - nothing yields "
                 f"below about {st.get('yields_at_g', 0):.1f} g")
    c.setFillColor(colors.HexColor("#0D1B2A"))
    c.setFont("Helvetica", 6.5)
    c.drawString(ox + 8, 48.0 + box_h - 26,
                 f"CARRIER {assembly.get('total_carrier_weight', 0):.0f} LB  |  "
                 f"MACHINE AND LOAD {st.get('payload_weight', 0):.0f} LB  |  "
                 f"TOTAL ON THE TRUCK {st.get('total_suspended_weight', 0):.0f} LB")
    c.drawString(ox + 8, 48.0 + box_h - 37,
                 "Welds: 3/16 fillet on the frame tubes, 1/4 on the mount beams, "
                 "sleeves and hinge barrels.")
    c.setFillColor(colors.HexColor("#D90429"))
    c.setFont("Helvetica-Bold", 6.5)
    c.drawString(ox + 8, 48.0 + box_h - 48,
                 "The sleeves over the mounting tubes are structural. Do not "
                 "leave them off.")


def draw_sheet_s9(dc: DraftingCanvas, params: ProjectParameters, assembly: Dict[str, Any], stock_data: Dict[str, Any]):
    """Sheet S9: Stock Cutting Plan & Material Purchasing Requirements"""
    dc.draw_border_and_title_block("S9", "STOCK CUTTING PLAN & PURCHASING OPTIMIZATION", 9, 9)
    c = dc.c
    
    ox = 55.0
    oy = 520.0
    
    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColor(colors.HexColor("#001D3D"))
    c.drawString(ox, oy, "STOCK CUTTING PLAN - CUT EACH STICK IN THIS ORDER")
    
    stock_plan = stock_data.get("stock_plan", [])
    column_x = (ox, 366.0)
    y_by_column = [oy - 22, oy - 22]
    
    for i, stick in enumerate(stock_plan):
        column = i % 2
        x = column_x[column]
        y = y_by_column[column]
            
        stk_id = stick.get("stick_id", f"STK-{i+1:02d}")
        sec = stick.get("section", "")
        grd = stick.get("grade", "A500 Gr B")
        stk_len = stick.get("stock_length", 240.0)
        parts = stick.get("parts", [])
        eff = stick.get("efficiency_pct", 0.0)
        scrap = stick.get("scrap_remaining", 0.0)
        
        c.setFont("Helvetica-Bold", 7.2)
        c.setFillColor(colors.HexColor("#0D1B2A"))
        c.drawString(x, y, f"{stk_id} - {sec} - {stk_len/12:.0f} FT STICK")
        y -= 10
        c.setFont("Helvetica-Bold", 6.2)
        c.setFillColor(colors.HexColor("#003566"))
        c.drawString(x, y, "CUT:")
        y -= 8
        c.setFont("Helvetica", 6.5)
        c.setFillColor(colors.black)
        for cut_number, part in enumerate(parts, start=1):
            c.drawString(x + 9, y,
                         f"{cut_number}. {part.get('piece_mark', '')} - "
                         f"{fraction_str(part.get('length', 0.0))}")
            y -= 8
        c.setFont("Helvetica-Bold", 6.5)
        c.setFillColor(colors.HexColor("#B7094C"))
        c.drawString(x, y, f"LEFT OVER: {fraction_str(scrap)}")
        y_by_column[column] = y - 16
        
    # ---- What to buy. Put the whole list on the sheet, in one column each,
    #      sized to what is actually there instead of a fixed five rows. ----
    purchase = stock_data.get("purchase_list", [])
    linear = [p for p in purchase if p.get("category") == "LINEAR_STOCK"]
    other = [p for p in purchase if p.get("category") != "LINEAR_STOCK"]

    def _row_text(prow):
        wt = prow.get("total_purchased_weight", 0.0)
        wt_str = f" - {wt:.0f} lb" if wt > 0 else ""
        return (f"{prow.get('quantity', 1)}x {prow.get('section', '')} "
                f"({prow.get('unit_size', '')}){wt_str}")

    lead = 7.6
    rows = max(len(linear), len(other))
    box_h = 26.0 + rows * lead
    purch_y = 46.0
    box_w = 400.0
    c.setFillColor(colors.HexColor("#F8F9FA"))
    c.setStrokeColor(colors.HexColor("#003566"))
    c.setLineWidth(1.0)
    c.rect(ox, purch_y, box_w, box_h, fill=1, stroke=1)
    c.setFont("Helvetica-Bold", 7.0)
    c.setFillColor(colors.HexColor("#003566"))
    c.drawString(ox + 8, purch_y + box_h - 11, "WHAT TO BUY")

    for x_off, heading, rowset in ((8.0, "STEEL BY THE STICK:", linear),
                                   (205.0, "PLATE, GRATING & HARDWARE:", other)):
        c.setFont("Helvetica-Bold", 5.5)
        c.setFillColor(colors.HexColor("#333333"))
        c.drawString(ox + x_off, purch_y + box_h - 21, heading)
        py = purch_y + box_h - 29
        c.setFont("Helvetica", 5.2)
        c.setFillColor(colors.black)
        for prow in rowset:
            c.drawString(ox + x_off, py,
                         "- " + _fit(c, _row_text(prow), 188.0, "Helvetica", 5.2))
            py -= lead

def generate_shop_drawings(params: ProjectParameters, assembly: Dict[str, Any], stock_data: Dict[str, Any], output_path: str):
    """Generates the complete 9-Sheet Vector Shop Drawing Set for US Letter Landscape."""
    c = canvas.Canvas(output_path, pagesize=landscape(letter), pageCompression=0)
    dc = DraftingCanvas(c)
    
    # Sheet 1: General Arrangement
    draw_sheet_s1(dc, params, assembly)
    c.showPage()
    
    # Sheet 2: Main Carrier Weldment - Plan
    draw_sheet_s2(dc, params, assembly)
    c.showPage()
    
    # Sheet 3: Main Carrier Weldment - Elevation & Sections
    draw_sheet_s3(dc, params, assembly)
    c.showPage()
    
    # Sheet 4: Twin Receiver Stinger Assembly
    draw_sheet_s4(dc, params, assembly)
    c.showPage()
    
    # Sheet 5: Ramp Weldment - Plan
    draw_sheet_s5(dc, params, assembly)
    c.showPage()
    
    # Sheet 6: Ramp Weldment - Elevation & Hinge
    draw_sheet_s6(dc, params, assembly)
    c.showPage()
    
    # Sheet 7: Individual Fabricated Parts
    draw_sheet_s7(dc, params, assembly)
    c.showPage()
    
    # Sheet 8: Material Schedule & BOM
    draw_sheet_s8(dc, params, assembly)
    c.showPage()
    
    # Sheet 9: Stock Cutting Plan
    draw_sheet_s9(dc, params, assembly, stock_data)
    c.showPage()
    
    c.save()
