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
        
        c.drawString(tb_x + 85, tb_y + 17, "REV: 0 (INITIAL BUILD)")
        c.drawString(tb_x + 85, tb_y + 8, "CAD: Z-SPRAY FABRICATOR")
        
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
            "CRITICAL: ALL DIMENSIONS GOVERN. VERIFY ALL UNVERIFIED FIELD MEASUREMENTS BEFORE CUTTING STEEL OR DRILLING."
        )

    def draw_unverified_banner(self, x: float, y: float, w: float, h: float, text: str):
        c = self.c
        c.setFillColor(colors.HexColor("#FFF3CD"))
        c.setStrokeColor(colors.HexColor("#FFC107"))
        c.setLineWidth(1.0)
        c.rect(x, y, w, h, fill=1, stroke=1)
        c.setFillColor(colors.HexColor("#856404"))
        c.setFont("Helvetica-Bold", 6.5)
        c.drawString(x + 6, y + h - 10, "[!] UNVERIFIED FIELD DIMENSION - MANDATORY CONFIRMATION")
        c.setFont("Helvetica", 6.0)
        # Handle multi-line
        lines = text.split("\n")
        line_y = y + h - 20
        for line in lines:
            c.drawString(x + 6, line_y, line)
            line_y -= 8

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
        c.setFont("Helvetica-Bold", 6.0)
        c.setFillColor(colors.HexColor("#001219"))
        tw = c.stringWidth(text, "Helvetica-Bold", 6.0)
        mid_x = (x1 + x2) / 2.0
        # White background box for text clarity
        c.setFillColor(colors.white)
        c.rect(mid_x - tw/2 - 2, y - 3, tw + 4, 7, fill=1, stroke=0)
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
        c.setFont("Helvetica-Bold", 6.0)
        mid_y = (y1 + y2) / 2.0
        c.saveState()
        c.translate(x, mid_y)
        c.rotate(90)
        tw = c.stringWidth(text, "Helvetica-Bold", 6.0)
        c.setFillColor(colors.white)
        c.rect(-tw/2 - 2, -3.5, tw + 4, 7, fill=1, stroke=0)
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
        r = 8.0
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
        c.setFont("Helvetica-Bold", 6.0)
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
    dc.draw_border_and_title_block("S1", "GENERAL ARRANGEMENT - PLAN, ELEVATION, & REAR", 1, 9)
    c = dc.c
    
    scale = 2.8
    ox = 115.0
    oy = 425.0
    
    # 1. PLAN VIEW
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.HexColor("#001D3D"))
    c.drawString(ox - 30, 540.0, "VIEW A: GENERAL ARRANGEMENT - PLAN VIEW")
    
    # Front Datum Reference Line (X=0)
    c.setStrokeColor(colors.HexColor("#D90429"))
    c.setLineWidth(1.0)
    c.setDash([6, 3])
    c.line(ox, oy - 65, ox, oy + 85)
    c.setDash([])
    c.setFont("Helvetica-Bold", 6.5)
    c.setFillColor(colors.HexColor("#D90429"))
    c.drawString(ox + 6, oy + 88, "FRONT DATUM X=0")
    
    # Twin Receiver Mounts
    stinger_w = 2.0 * scale
    stinger_span = params.receiver_spacing * scale
    for y_sign in [-1, 1]:
        sy = oy + y_sign * (stinger_span / 2.0) - (stinger_w / 2.0)
        c.setFillColor(colors.HexColor("#CED4DA"))
        c.setStrokeColor(colors.HexColor("#495057"))
        c.setLineWidth(1.0)
        c.rect(ox - (18.0 * scale), sy, 18.0 * scale + (18.0 * scale), stinger_w, fill=1, stroke=1)
        # Hitch Pin Hole
        hole_x = ox - (18.0 - params.hitch_pin_hole_setback) * scale
        c.setFillColor(colors.HexColor("#D90429"))
        c.circle(hole_x, sy + stinger_w/2, 1.8, fill=1, stroke=1)
        
    # Carrier Deck Outline (38" wide x 63" long)
    deck_l = params.carrier_deck_length * scale
    deck_w = params.carrier_width * scale
    
    # Dual Wheel Tracks (12" wide each, 14" center gap)
    track_w = params.track_flat_width * scale
    c.setFillColor(colors.HexColor("#E9ECEF"))
    c.setStrokeColor(colors.black)
    c.setLineWidth(1.2)
    c.rect(ox, oy - deck_w/2.0, deck_l, track_w, fill=1, stroke=1)
    c.rect(ox, oy + deck_w/2.0 - track_w, deck_l, track_w, fill=1, stroke=1)
    
    # Open center gap
    c.setFillColor(colors.HexColor("#F8F9FA"))
    c.setStrokeColor(colors.HexColor("#6C757D"))
    c.setLineWidth(0.5)
    c.rect(ox, oy - deck_w/2.0 + track_w, deck_l, deck_w - 2 * track_w, fill=1, stroke=1)
    c.setFont("Helvetica", 6.0)
    c.setFillColor(colors.HexColor("#6C757D"))
    c.drawCentredString(ox + deck_l/2, oy - 2, "OPEN CLEANOUT GAP (14\" CLEAR)")
    
    # Machine Envelope Footprint (36" wide x 72" practical length)
    mach_l = params.machine_length_field * scale
    mach_w = params.machine_width * scale
    c.setStrokeColor(colors.HexColor("#0077B6"))
    c.setLineWidth(0.8)
    c.setDash([4, 2])
    c.rect(ox + (2.0 * scale), oy - mach_w/2.0, mach_l, mach_w, fill=0, stroke=1)
    c.setDash([])
    c.setFont("Helvetica-Bold", 6.0)
    c.setFillColor(colors.HexColor("#0077B6"))
    c.drawString(ox + 8, oy + mach_w/2.0 - 8, "Z-SPRAY JUNIOR ENVELOPE (36\" W x 72\" L)")
    
    # Rear Tires resting location
    rear_tire_x = ox + (deck_l - 1.0 * scale - 11.0 * scale)
    for y_sign in [-1, 1]:
        c.setFillColor(colors.HexColor("#343A40"))
        c.rect(rear_tire_x, oy + y_sign * (13.0 * scale) - (4.25 * scale), 11.0 * scale, 8.5 * scale, fill=1, stroke=1)
        
    # Ramp Hinge Line at X = 63.0"
    hx = ox + deck_l
    dc.draw_centerline(hx, oy - deck_w/2 - 12, hx, oy + deck_w/2 + 12)
    c.setFont("Helvetica-Bold", 6.0)
    c.setFillColor(colors.HexColor("#D90429"))
    c.drawString(hx + 3, oy + deck_w/2 + 6, "RAMP HINGE (X=63\")")
    
    # Deployed ramp outline
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
    dc.draw_dim_h(ox, hx, oy + deck_w/2 + 20, f"CARRIER DECK = {fraction_str(params.carrier_deck_length)}")
    dc.draw_dim_h(hx, hx + ramp_l, oy + deck_w/2 + 20, f"RAMP = {fraction_str(params.ramp_length)}")
    dc.draw_dim_v(oy - deck_w/2, oy + deck_w/2, ox - 28, f"WIDTH = {fraction_str(params.carrier_width)}")
    dc.draw_dim_v(oy - deck_w/2, oy - deck_w/2 + track_w, ox - 14, f"TRACK = {fraction_str(params.track_flat_width)}")
    dc.draw_dim_v(oy - stinger_span/2, oy + stinger_span/2, ox - 44, f"RECEIVER C-C = {fraction_str(params.receiver_spacing)}")
    
    # 1.0" Rear Ramp Clearance Callout
    dc.draw_dim_h(rear_tire_x + 11.0 * scale, hx, oy - deck_w/2 - 12, "1.0\" NOM. CLEARANCE", ext_down=True)
    
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
    c.line(ox - 25, ground_y, hx + dx + 15, ground_y)
    c.setFont("Helvetica-Bold", 6.0)
    c.setFillColor(colors.HexColor("#6C757D"))
    c.drawString(ox - 25, ground_y + 4, "GROUND LEVEL (Z=-17\")")
    
    # Carrier Frame Tube
    c.setStrokeColor(colors.black)
    c.setLineWidth(1.2)
    c.setFillColor(colors.HexColor("#DEE2E6"))
    c.rect(ox, e_oy - (2.0 * scale), deck_l, 2.0 * scale, fill=1, stroke=1)
    # Flared Guide 3" high
    c.setFillColor(colors.HexColor("#ADB5BD"))
    c.rect(ox, e_oy, deck_l, 3.0 * scale, fill=1, stroke=1)
    
    # Upright Ramp
    c.setFillColor(colors.HexColor("#CED4DA"))
    c.rect(hx - (2.0 * scale), e_oy, 2.0 * scale, ramp_l, fill=1, stroke=1)
    c.setFont("Helvetica-Bold", 6.0)
    c.setFillColor(colors.HexColor("#343A40"))
    c.drawString(hx + 4, e_oy + ramp_l - 12, "UPRIGHT POSITION (90°)")
    
    # Deployed Ramp Line
    c.setStrokeColor(colors.HexColor("#4361EE"))
    c.setLineWidth(1.2)
    c.line(hx, e_oy, hx + dx, ground_y)
    c.setFont("Helvetica-Bold", 6.0)
    c.setFillColor(colors.HexColor("#4361EE"))
    c.drawString(hx + 35, ground_y + 8, f"DEPLOYED SLOPE = {assembly.get('ramp_angle_deg', 16.2)}°")
    
    # Stingers underframe & truck extension
    c.setFillColor(colors.HexColor("#6C757D"))
    c.rect(ox - (18.0 * scale), e_oy - (4.0 * scale), 36.0 * scale, 2.0 * scale, fill=1, stroke=1)
    
    # Elevation Dimensions
    dc.draw_dim_v(ground_y, e_oy, ox - 35, f"DECK HT = {fraction_str(params.deck_height)}")
    dc.draw_dim_v(e_oy, e_oy + (3.0 * scale), ox - 18, f"GUIDE = {fraction_str(params.flared_guide_height)}")
    dc.draw_dim_v(e_oy, e_oy + ramp_l, hx + 22, f"RAMP HT = {fraction_str(params.ramp_length)}")
    
    # Unverified Banner on S1 (cleanly on left bottom)
    dc.draw_unverified_banner(
        ox - 30, 45, 360, 36,
        "STINGER INSERTION (18.0\") & PIN HOLE (3.0\") ARE PROVISIONAL DESIGN ESTIMATES.\n"
        "MANDATORY: FIELD VERIFY MEASUREMENTS ON FORD F-350 TRUCK RECEIVERS BEFORE CUTTING."
    )

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
    deck_w = params.carrier_width * scale
    m_thk = 2.0 * scale
    
    # Longitudinal Frame Tubes M1-L and M1-R
    c.setFillColor(colors.HexColor("#E9ECEF"))
    c.setStrokeColor(colors.black)
    c.setLineWidth(1.2)
    c.rect(ox, oy - deck_w/2.0, deck_l, m_thk, fill=1, stroke=1)
    c.rect(ox, oy + deck_w/2.0 - m_thk, deck_l, m_thk, fill=1, stroke=1)
    
    # Inner Track Support Angles M2-L, M2-R
    c.setFillColor(colors.HexColor("#DEE2E6"))
    c.rect(ox, oy - (7.0 * scale) - m_thk, deck_l, m_thk, fill=1, stroke=1)
    c.rect(ox, oy + (7.0 * scale), deck_l, m_thk, fill=1, stroke=1)
    
    # Crossmembers C1-C4
    cm_locs = [
        ("C1", 1.00, "C1"),
        ("C2", 18.00, "C2"),
        ("C3", 38.00, "C3"),
        ("C4", 62.00, "C4")
    ]
    c_span = (params.carrier_width - 4.0) * scale
    c_span_y = oy - deck_w/2.0 + m_thk
    
    for mark, x_loc, desc in cm_locs:
        cx = ox + (x_loc * scale) - (m_thk / 2.0)
        c.setFillColor(colors.HexColor("#CED4DA"))
        c.setStrokeColor(colors.black)
        c.setLineWidth(1.0)
        c.rect(cx, c_span_y, m_thk, c_span, fill=1, stroke=1)
        dc.draw_centerline(cx + m_thk/2, c_span_y - 6, cx + m_thk/2, c_span_y + c_span + 6)
        
    # Front Stop Angles G5
    c.setFillColor(colors.HexColor("#6C757D"))
    c.rect(ox + (2.0 * scale), oy - deck_w/2.0, 1.5 * scale, 12.0 * scale, fill=1, stroke=1)
    c.rect(ox + (2.0 * scale), oy + deck_w/2.0 - (12.0 * scale), 1.5 * scale, 12.0 * scale, fill=1, stroke=1)
    
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
    dc.draw_dim_v(oy - deck_w/2, oy + deck_w/2, ox - 38, f"OVERALL WIDTH = {fraction_str(params.carrier_width)}")
    dc.draw_dim_v(oy - deck_w/2 + m_thk, oy + deck_w/2 - m_thk, ox - 24, f"CROSSMEMBER = {fraction_str(params.carrier_width - 4.0)}")
    dc.draw_dim_v(oy - deck_w/2, oy - (7.0 * scale), ox - 12, f"TRACK = {fraction_str(params.track_flat_width)}")
    
    # Piece Mark Balloons
    dc.draw_balloon(ox + 70, oy + deck_w/2 + 8, "M1-R", leader_to=(ox + 70, oy + deck_w/2 - m_thk/2))
    dc.draw_balloon(ox + 70, oy - deck_w/2 - 14, "M1-L", leader_to=(ox + 70, oy - deck_w/2 + m_thk/2))
    dc.draw_balloon(ox + (18.00 * scale) + 10, oy - 20, "C2", leader_to=(ox + (18.00 * scale), oy - 6))
    dc.draw_balloon(ox + (38.00 * scale) + 10, oy - 20, "C3", leader_to=(ox + (38.00 * scale), oy - 6))
    dc.draw_balloon(ox + (62.00 * scale) - 12, oy - 20, "C4", leader_to=(ox + (62.00 * scale), oy - 6))
    dc.draw_balloon(ox + 22, oy + 4, "G4", leader_to=(ox + 6, oy))
    
    # Weld Notes
    dc.draw_weld_callout(ox + 130, oy + 40, "3/16 FILLET ALL AROUND (TYP)", leader_to=(ox + (18.00 * scale), oy + deck_w/2 - m_thk))
    dc.draw_weld_callout(ox + 210, oy - deck_w/2 - 28, "3/16 FILLET BOTH SIDES", leader_to=(ox + (38.00 * scale), oy - deck_w/2 + m_thk))

def draw_sheet_s3(dc: DraftingCanvas, params: ProjectParameters, assembly: Dict[str, Any]):
    """Sheet S3: Main Carrier Weldment - Elevation & Sections"""
    dc.draw_border_and_title_block("S3", "MAIN CARRIER WELDMENT - ELEVATION & SECTIONS", 3, 9)
    c = dc.c
    
    ox = 175.0
    oy = 380.0
    scale = 4.8
    
    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColor(colors.HexColor("#001D3D"))
    c.drawString(ox - 90, 535.0, "MAIN CARRIER WELDMENT - SIDE ELEVATION & SECTION A-A")
    
    # Front Datum
    dc.draw_centerline(ox, oy - 50, ox, oy + 60)
    c.setFont("Helvetica-Bold", 6.5)
    c.setFillColor(colors.HexColor("#D90429"))
    c.drawString(ox - 20, oy + 64, "FRONT DATUM X=0")
    
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
    
    # Stingers underframe
    stinger_ins = params.stinger_insertion_length * scale
    stinger_ovl = params.stinger_overlap_length * scale
    c.setFillColor(colors.HexColor("#CED4DA"))
    c.rect(ox - stinger_ins, oy - (2 * m_thk), stinger_ins + stinger_ovl, m_thk, fill=1, stroke=1)
    
    # Stinger Gusset G1
    c.setFillColor(colors.HexColor("#495057"))
    dc.draw_polygon([(ox, oy - m_thk), (ox + (8.0 * scale), oy - m_thk), (ox, oy - (2 * m_thk))], fill=1, stroke=1)
    
    # Hinge Sleeves at Rear
    c.setFillColor(colors.HexColor("#343A40"))
    c.circle(ox + deck_l, oy - m_thk/2, 4.5, fill=1, stroke=1)
    
    # Elevation Dimensions
    dc.draw_dim_v(oy - m_thk, oy, ox - stinger_ins - 15, "2\" TUBE")
    dc.draw_dim_v(oy - 2*m_thk, oy, ox - stinger_ins - 32, "4\" TUBE+STINGER")
    dc.draw_dim_v(oy, oy + guide_h, ox + deck_l + 20, f"GUIDE = {fraction_str(params.flared_guide_height)}")
    dc.draw_dim_h(ox - stinger_ins, ox, oy - 2*m_thk - 22, f"INSERTION = {fraction_str(params.stinger_insertion_length)} [UNVERIFIED]")
    dc.draw_dim_h(ox, ox + stinger_ovl, oy - 2*m_thk - 22, f"OVERLAP = {fraction_str(params.stinger_overlap_length)}")
    dc.draw_dim_h(ox, ox + deck_l, oy + guide_h + 16, f"OVERALL DECK = {fraction_str(params.carrier_deck_length)}")
    
    # SECTION A-A (Enlarged Detail)
    sec_x = 120.0
    sec_y = 135.0
    sec_scale = 11.0
    
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(colors.HexColor("#001D3D"))
    c.drawString(sec_x, sec_y + 105, "SECTION A-A: WHEEL TRACK & FORMED 45-DEG FLARED GUIDE")
    
    # Outer Tube M1
    c.setFillColor(colors.HexColor("#DEE2E6"))
    c.setStrokeColor(colors.black)
    c.setLineWidth(1.2)
    c.rect(sec_x, sec_y, 2.0 * sec_scale, 2.0 * sec_scale, fill=1, stroke=1)
    
    # Inner Support Angle M2
    track_span = params.track_flat_width * sec_scale
    c.rect(sec_x + track_span - (2.0 * sec_scale), sec_y, 2.0 * sec_scale, 2.0 * sec_scale, fill=1, stroke=1)
    
    # Grating line
    c.setStrokeColor(colors.HexColor("#495057"))
    c.setLineWidth(1.5)
    c.line(sec_x, sec_y + 2.0 * sec_scale, sec_x + track_span, sec_y + 2.0 * sec_scale)
    
    # Formed Guide
    g_start_x = sec_x
    g_start_y = sec_y + 2.0 * sec_scale
    g_vert_y = g_start_y + (3.0 * sec_scale)
    g_flare_x = g_start_x - (1.5 * sec_scale)
    g_flare_y = g_vert_y + (1.5 * sec_scale)
    
    c.setStrokeColor(colors.black)
    c.setLineWidth(2.0)
    c.line(g_start_x, g_start_y, g_start_x, g_vert_y)
    c.line(g_start_x, g_vert_y, g_flare_x, g_flare_y)
    
    # Section Dimensions
    dc.draw_dim_h(sec_x, sec_x + track_span, sec_y - 14, f"TRACK FLAT WIDTH = {fraction_str(params.track_flat_width)}")
    dc.draw_dim_v(g_start_y, g_vert_y, sec_x + track_span + 14, "3.0\" VERTICAL")
    dc.draw_dim_h(g_flare_x, g_start_x, g_flare_y + 8, "1.5\" FLARE")
    
    dc.draw_balloon(sec_x - 25, g_vert_y + 4, "FG1-L", leader_to=(g_start_x, g_vert_y))
    dc.draw_balloon(sec_x - 18, sec_y + 10, "M1-L", leader_to=(sec_x, sec_y + 10))
    dc.draw_balloon(sec_x + track_span + 18, sec_y + 10, "M2-L", leader_to=(sec_x + track_span, sec_y + 10))

def draw_sheet_s4(dc: DraftingCanvas, params: ProjectParameters, assembly: Dict[str, Any]):
    """Sheet S4: Twin Receiver / Stinger Assembly"""
    dc.draw_border_and_title_block("S4", "TWIN RECEIVER / TRUCK INTERFACE ASSEMBLY", 4, 9)
    c = dc.c
    
    ox = 215.0
    oy = 310.0
    scale = 5.4
    
    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColor(colors.HexColor("#001D3D"))
    c.drawString(ox - 150, 535.0, "TWIN STINGER MOUNTING INTERFACE - PLAN & HOLE LOCATIONS")
    
    spacing = params.receiver_spacing * scale
    tube_w = params.receiver_tube_width * scale
    ins_l = params.stinger_insertion_length * scale
    ovl_l = params.stinger_overlap_length * scale
    tot_l = ins_l + ovl_l
    
    # Front Datum Line
    dc.draw_centerline(ox, oy - spacing/2 - 25, ox, oy + spacing/2 + 25)
    c.setFont("Helvetica-Bold", 6.5)
    c.setFillColor(colors.HexColor("#D90429"))
    c.drawCentredString(ox, oy + spacing/2 + 30, "FRONT CARRIER FACE (X = 0.0\")")
    
    # Stingers S1-L and S1-R
    for y_sign in [-1, 1]:
        sy = oy + y_sign * (spacing / 2.0) - (tube_w / 2.0)
        c.setFillColor(colors.HexColor("#CED4DA"))
        c.setStrokeColor(colors.black)
        c.setLineWidth(1.2)
        c.rect(ox - ins_l, sy, tot_l, tube_w, fill=1, stroke=1)
        dc.draw_centerline(ox - ins_l - 10, sy + tube_w/2, ox + ovl_l + 10, sy + tube_w/2)
        
        # 5/8" Pin hole
        pin_x = ox - ins_l + (params.hitch_pin_hole_setback * scale)
        c.setFillColor(colors.HexColor("#D90429"))
        c.circle(pin_x, sy + tube_w/2, 2.5, fill=1, stroke=1)
        
        # Gussets G1
        c.setFillColor(colors.HexColor("#6C757D"))
        dc.draw_polygon([(ox, sy), (ox + (8.0 * scale), sy), (ox, sy + (y_sign * -4.0 * scale))], fill=1, stroke=1)
        
    # C1 and C2 Crossmembers
    c.setStrokeColor(colors.HexColor("#0D1B2A"))
    c.setLineWidth(1.2)
    c.setFillColor(colors.HexColor("#ADB5BD"))
    c.rect(ox, oy - spacing/2 - tube_w/2, 2.0 * scale, spacing + tube_w, fill=1, stroke=1)
    c.rect(ox + (18.0 * scale) - 2.0*scale, oy - spacing/2 - tube_w/2, 2.0 * scale, spacing + tube_w, fill=1, stroke=1)
    
    # Dimensions
    dc.draw_dim_v(oy - spacing/2, oy + spacing/2, ox - ins_l - 25, f"RECEIVER C-C = {fraction_str(params.receiver_spacing)} (EXACT)")
    dc.draw_dim_v(oy - spacing/2 - tube_w/2, oy + spacing/2 + tube_w/2, ox - ins_l - 42, f"OUTSIDE SPAN = {fraction_str(params.receiver_outside_span)} (EXACT)")
    dc.draw_dim_h(ox - ins_l, ox, oy + spacing/2 + 16, f"INSERTION = {fraction_str(params.stinger_insertion_length)} [UNVERIFIED]")
    dc.draw_dim_h(ox - ins_l, ox - ins_l + (params.hitch_pin_hole_setback * scale), oy - spacing/2 - 30, f"PIN HOLE = {fraction_str(params.hitch_pin_hole_setback)} [UNVERIFIED]")
    dc.draw_dim_h(ox, ox + ovl_l, oy + spacing/2 + 16, f"OVERLAP = {fraction_str(params.stinger_overlap_length)}")
    
    dc.draw_balloon(ox + 50, oy - spacing/2 + 25, "S1-L", leader_to=(ox + 35, oy - spacing/2 + tube_w/2))
    dc.draw_balloon(ox + 50, oy + spacing/2 - 25, "S1-R", leader_to=(ox + 35, oy + spacing/2 - tube_w/2))
    dc.draw_balloon(ox + 18, oy - spacing/2 - 16, "G1", leader_to=(ox + 8, oy - spacing/2 - 2))
    
    # Clean Unverified Warning Banner at bottom left (Zero overlap with title block)
    dc.draw_unverified_banner(
        50.0, 45.0, 415.0, 52.0,
        "1. CONFIRM TRUCK RECEIVER INTERNAL STOP DISTANCE: MEASURE DEPTH FROM RECEIVER FACE TO PREVENT BOTTOMING OUT.\n"
        "2. CONFIRM HITCH PIN HOLE LOCATION (MEASURE FROM RECEIVER FACE TO 5/8\" HOLE CENTERLINE ON FORD F-350).\n"
        "3. PROVISIONAL 18\" INSERTION AND 3\" PIN HOLE DISTANCES MUST BE FIELD-CONFIRMED PRIOR TO DRILLING."
    )

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
    deck_w = params.carrier_width * scale
    m_thk = 2.0 * scale
    
    # Outer Side Tubes R1-L and R1-R
    c.setFillColor(colors.HexColor("#E9ECEF"))
    c.setStrokeColor(colors.black)
    c.setLineWidth(1.2)
    c.rect(ox, oy - deck_w/2.0, ramp_l, m_thk, fill=1, stroke=1)
    c.rect(ox, oy + deck_w/2.0 - m_thk, ramp_l, m_thk, fill=1, stroke=1)
    
    # Inner Support Rails R2-L and R2-R
    c.setFillColor(colors.HexColor("#DEE2E6"))
    c.rect(ox, oy - (7.0 * scale) - m_thk, ramp_l, m_thk, fill=1, stroke=1)
    c.rect(ox, oy + (7.0 * scale), ramp_l, m_thk, fill=1, stroke=1)
    
    # Ramp Crossmembers RC1 to RC5
    rc_locs = [
        ("RC1", 0.50, "RC1"),
        ("RC2", 15.00, "RC2"),
        ("RC3", 30.00, "RC3"),
        ("RC4", 45.00, "RC4"),
        ("RC5", 60.00, "RC5")
    ]
    rc_span = (params.carrier_width - 4.0) * scale
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
    dc.draw_dim_v(oy - deck_w/2, oy + deck_w/2, ox - 35, f"OVERALL WIDTH = {fraction_str(params.carrier_width)}")
    dc.draw_dim_v(oy - deck_w/2, oy - (7.0 * scale), ox - 18, f"TRACK = {fraction_str(params.track_flat_width)}")
    
    # Balloons
    dc.draw_balloon(ox + 55, oy + deck_w/2 + 8, "R1-R", leader_to=(ox + 55, oy + deck_w/2 - m_thk/2))
    dc.draw_balloon(ox + 55, oy - deck_w/2 - 14, "R1-L", leader_to=(ox + 55, oy - deck_w/2 + m_thk/2))
    dc.draw_balloon(ox + (30.00 * scale) + 10, oy - 18, "RC3", leader_to=(ox + (30.00 * scale), oy))
    dc.draw_balloon(ox + ramp_l + 10, oy, "RF1", leader_to=(ox + ramp_l, oy))

def draw_sheet_s6(dc: DraftingCanvas, params: ProjectParameters, assembly: Dict[str, Any]):
    """Sheet S6: Ramp Weldment - Elevation & Hinge Detail"""
    dc.draw_border_and_title_block("S6", "RAMP ELEVATION, DEPLOYMENT ANGLE, & HINGE DETAIL", 6, 9)
    c = dc.c
    
    scale = 3.6
    ox = 140.0
    oy = 260.0
    
    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColor(colors.HexColor("#001D3D"))
    c.drawString(ox - 60, 535.0, "RAMP ELEVATION: 90° UPRIGHT TRANSPORT & 16.2° DEPLOYED PROFILES")
    
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
    c.line(ox - 30, ground_y, ox + dx + 100, ground_y)
    c.setFont("Helvetica-Bold", 6.0)
    c.setFillColor(colors.HexColor("#6C757D"))
    c.drawString(ox + dx + 12, ground_y + 4, "GROUND LEVEL (Z = -17\")")
    
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
    c.drawString(ox + 4, oy + ramp_l - 12, "UPRIGHT TRANSPORT POSITION (90 DEG)")
    
    # Dims
    dc.draw_dim_v(ground_y, oy, ox - 20, f"DECK = {fraction_str(params.deck_height)}")
    dc.draw_dim_v(oy, oy + ramp_l, ox - 20, f"UPRIGHT = {fraction_str(params.ramp_length)}")
    dc.draw_dim_h(ox, ox + dx, ground_y - 16, f"GROUND HORIZ SPAN = {fraction_str(dx/scale)}")
    
    # ENLARGED HINGE DETAIL VIEW (Clean in lower-right)
    det_x = 420.0
    det_y = 140.0
    det_scale = 13.0
    
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(colors.HexColor("#001D3D"))
    c.drawString(det_x - 30, det_y + 110, "DETAIL B: HINGE SLEEVE & 3/4\" PIN ARRANGEMENT")
    
    # Carrier rear tube (2x2)
    c.setFillColor(colors.HexColor("#DEE2E6"))
    c.setStrokeColor(colors.black)
    c.rect(det_x - (2.0 * det_scale), det_y, 2.0 * det_scale, 2.0 * det_scale, fill=1, stroke=1)
    
    # Hinge Ears G3
    c.setFillColor(colors.HexColor("#ADB5BD"))
    c.rect(det_x, det_y + 0.25*det_scale, 1.5 * det_scale, 1.5 * det_scale, fill=1, stroke=1)
    
    # DOM Sleeve
    c.setFillColor(colors.HexColor("#495057"))
    c.circle(det_x + 0.75 * det_scale, det_y + 1.0 * det_scale, 0.5625 * det_scale, fill=1, stroke=1)
    
    # 3/4" Pin
    c.setFillColor(colors.HexColor("#D90429"))
    c.circle(det_x + 0.75 * det_scale, det_y + 1.0 * det_scale, 0.375 * det_scale, fill=1, stroke=1)
    
    dc.draw_dim_h(det_x, det_x + 1.5*det_scale, det_y - 12, "1.5\" EAR PROJECTION")
    dc.draw_balloon(det_x + 35, det_y + 70, "P1", leader_to=(det_x + 0.75 * det_scale, det_y + 1.0 * det_scale))
    dc.draw_balloon(det_x - 30, det_y + 40, "C4", leader_to=(det_x - 1.0 * det_scale, det_y + 1.0 * det_scale))
    dc.draw_weld_callout(det_x + 50, det_y + 15, "1/4 FILLET ALL AROUND SLEEVE", leader_to=(det_x + 0.75 * det_scale + 4, det_y + 1.0 * det_scale - 4))

def draw_sheet_s7(dc: DraftingCanvas, params: ProjectParameters, assembly: Dict[str, Any]):
    """Sheet S7: Individual Fabricated Parts, Gussets, & Brackets"""
    dc.draw_border_and_title_block("S7", "INDIVIDUAL FABRICATED PARTS - GUSSETS, GUARDS, & BRACKETS", 7, 9)
    c = dc.c
    
    scale = 14.0
    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColor(colors.HexColor("#001D3D"))
    c.drawString(60.0, 535.0, "INDIVIDUAL FABRICATED PARTS - SHEAR, LASER, & DRILL DETAILS")
    
    # Row 1, Column 1: G1 Stinger Gusset
    g1_x = 75.0
    g1_y = 370.0
    c.setFont("Helvetica-Bold", 8.0)
    c.setFillColor(colors.HexColor("#001D3D"))
    c.drawString(g1_x, g1_y + 75, "PART G1: STINGER GUSSET (QTY: 4)")
    c.setFont("Helvetica", 6.0)
    c.drawString(g1_x, g1_y + 66, "1/4\" A36 PLATE - SHEAR CUT")
    
    c.setFillColor(colors.HexColor("#E9ECEF"))
    c.setStrokeColor(colors.black)
    c.setLineWidth(1.2)
    dc.draw_polygon([(g1_x, g1_y), (g1_x + (8.0 * scale/2), g1_y), (g1_x, g1_y + (4.0 * scale/2))], fill=1, stroke=1)
    dc.draw_dim_h(g1_x, g1_x + (8.0 * scale/2), g1_y - 12, "8.0\" BASE")
    dc.draw_dim_v(g1_y, g1_y + (4.0 * scale/2), g1_x - 12, "4.0\" HT")
    dc.draw_balloon(g1_x + 22, g1_y + 12, "G1")
    
    # Row 1, Column 2: G2 Rear Light Guard Plate
    g2_x = 285.0
    g2_y = 370.0
    c.setFont("Helvetica-Bold", 8.0)
    c.drawString(g2_x, g2_y + 75, "PART G2-L/R: REAR LIGHT GUARD (QTY: 2)")
    c.setFont("Helvetica", 6.0)
    c.drawString(g2_x, g2_y + 66, "3/16\" A36 PLATE - OVAL OPENING")
    
    gw = 8.0 * scale/2
    gh = 6.0 * scale/2
    c.setFillColor(colors.HexColor("#E9ECEF"))
    c.rect(g2_x, g2_y, gw, gh, fill=1, stroke=1)
    
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor("#D90429"))
    c.roundRect(g2_x + gw/2 - (6.75*scale/4), g2_y + gh/2 - (2.5*scale/4), 6.75*scale/2, 2.5*scale/2, 8, fill=1, stroke=1)
    c.setFont("Helvetica-Bold", 5.5)
    c.setFillColor(colors.HexColor("#D90429"))
    c.drawCentredString(g2_x + gw/2, g2_y + gh/2 + 2, "6.75\" x 2.50\"")
    c.drawCentredString(g2_x + gw/2, g2_y + gh/2 - 6, "OVAL LED CUTOUT")
    
    dc.draw_dim_h(g2_x, g2_x + gw, g2_y - 12, "8.0\" WIDTH")
    dc.draw_dim_v(g2_y, g2_y + gh, g2_x - 12, "6.0\" HEIGHT")
    dc.draw_balloon(g2_x + gw + 18, g2_y + gh/2, "G2", leader_to=(g2_x + gw, g2_y + gh/2))
    
    # Row 1, Column 3: G3 Hinge Mounting Ears
    g3_x = 495.0
    g3_y = 370.0
    c.setFont("Helvetica-Bold", 8.0)
    c.drawString(g3_x, g3_y + 75, "PART G3: HINGE EAR (QTY: 4)")
    c.setFont("Helvetica", 6.0)
    c.drawString(g3_x, g3_y + 66, "3/8\" A36 PLATE - 25/32\" HOLE")
    
    ew = 2.5 * scale/2
    eh = 4.5 * scale/2
    c.setFillColor(colors.HexColor("#E9ECEF"))
    c.setStrokeColor(colors.black)
    c.rect(g3_x, g3_y, ew, eh, fill=1, stroke=1)
    c.setFillColor(colors.white)
    c.circle(g3_x + ew/2, g3_y + eh - 10, 0.781*scale/4, fill=1, stroke=1)
    dc.draw_dim_h(g3_x, g3_x + ew, g3_y - 12, "2.5\" W")
    dc.draw_dim_v(g3_y, g3_y + eh, g3_x - 12, "4.5\" L")
    dc.draw_balloon(g3_x + ew/2, g3_y + 12, "G3")
    
    # Row 2, Column 1: G4 Front Chain Tie-Down Bracket
    g4_x = 95.0
    g4_y = 180.0
    c.setFont("Helvetica-Bold", 8.0)
    c.drawString(g4_x, g4_y + 75, "PART G4: CHAIN TIE-DOWN (QTY: 1)")
    c.setFont("Helvetica", 6.0)
    c.drawString(g4_x, g4_y + 66, "3/8\" A36 PLATE - 1.00\" HOLE")
    
    cw = 4.0 * scale/2
    ch = 5.0 * scale/2
    c.setFillColor(colors.HexColor("#E9ECEF"))
    c.rect(g4_x, g4_y, cw, ch, fill=1, stroke=1)
    c.setFillColor(colors.white)
    c.circle(g4_x + cw/2, g4_y + ch/2, 1.0*scale/4, fill=1, stroke=1)
    dc.draw_dim_h(g4_x, g4_x + cw, g4_y - 12, "4.0\" W")
    dc.draw_dim_v(g4_y, g4_y + ch, g4_x - 12, "5.0\" H")
    dc.draw_balloon(g4_x + cw/2, g4_y + 12, "G4")
    
    # Row 2, Column 2: G5 Front Wheel Stop Angles
    g5_x = 285.0
    g5_y = 180.0
    c.setFont("Helvetica-Bold", 8.0)
    c.drawString(g5_x, g5_y + 75, "PART G5-L/R: WHEEL STOP (QTY: 2)")
    c.setFont("Helvetica", 6.0)
    c.drawString(g5_x, g5_y + 66, "L 2x2x1/4 A36 - 12.0\" CUT")
    
    c.setFillColor(colors.HexColor("#E9ECEF"))
    c.rect(g5_x, g5_y, 12.0 * scale/3, 2.0 * scale/3, fill=1, stroke=1)
    dc.draw_dim_h(g5_x, g5_x + 12.0 * scale/3, g5_y - 12, "12.0\" CUT")
    dc.draw_balloon(g5_x + 15, g5_y + 12, "G5")

def draw_sheet_s8(dc: DraftingCanvas, params: ProjectParameters, assembly: Dict[str, Any]):
    """Sheet S8: Material Schedule & Bill of Materials"""
    dc.draw_border_and_title_block("S8", "BILL OF MATERIALS & FABRICATION SCHEDULE", 8, 9)
    c = dc.c
    
    ox = 55.0
    oy = 520.0
    
    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColor(colors.HexColor("#001D3D"))
    c.drawString(ox, oy, "BILL OF MATERIALS - COMPLETE PIECE & CUT SCHEDULE")
    
    cols = [
        ("MARK", 42),
        ("DESCRIPTION", 130),
        ("ASSY", 60),
        ("SECTION / SIZE", 95),
        ("GRADE", 75),
        ("CUT LENGTH", 55),
        ("QTY", 28),
        ("WT (LB)", 45),
        ("NOTES", 130)
    ]
    
    y = oy - 18
    c.setFillColor(colors.HexColor("#003566"))
    c.rect(ox, y - 4, 660, 15, fill=1, stroke=0)
    
    cur_x = ox + 4
    c.setFont("Helvetica-Bold", 6.5)
    c.setFillColor(colors.white)
    for name, w in cols:
        c.drawString(cur_x, y, name)
        cur_x += w
        
    y -= 13
    bom = assembly.get("bom", [])
    tot_wt = 0.0
    
    c.setFont("Helvetica", 6.0)
    for i, row in enumerate(bom):
        # Stop table well above title block area
        if y < 140:
            break
        bg = colors.HexColor("#F8F9FA") if i % 2 == 0 else colors.white
        c.setFillColor(bg)
        c.rect(ox, y - 3, 660, 11, fill=1, stroke=0)
        
        c.setFillColor(colors.black)
        cur_x = ox + 4
        c.setFont("Helvetica-Bold", 6.0)
        c.drawString(cur_x, y, row.get("piece_mark", ""))
        cur_x += 42
        
        c.setFont("Helvetica", 6.0)
        c.drawString(cur_x, y, row.get("description", "")[:28])
        cur_x += 130
        c.drawString(cur_x, y, row.get("assembly", ""))
        cur_x += 60
        c.drawString(cur_x, y, row.get("size", "")[:18])
        cur_x += 95
        c.drawString(cur_x, y, row.get("grade", "")[:15])
        cur_x += 75
        c.drawString(cur_x, y, fraction_str(row.get("cut_length", 0.0)))
        cur_x += 55
        c.drawString(cur_x, y, str(row.get("quantity", 1)))
        cur_x += 28
        wt = float(row.get("total_weight", 0.0))
        tot_wt += wt
        c.drawString(cur_x, y, f"{wt:.1f}")
        cur_x += 45
        c.drawString(cur_x, y, row.get("notes", "")[:35])
        
        y -= 11
        
    # Total Weight Summary Box cleanly on the left (Zero overlap with title block)
    c.setFillColor(colors.HexColor("#E0AAFF"))
    c.rect(ox, 50.0, 410.0, 45.0, fill=1, stroke=1)
    c.setFillColor(colors.HexColor("#240046"))
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(ox + 10, 80.0, f"TOTAL ESTIMATED CARRIER STEEL DEAD WEIGHT: {tot_wt:.1f} LBS")
    c.setFont("Helvetica", 6.5)
    c.drawString(ox + 10, 68.0, "Includes all structural tubes, angles, plate gussets, light guards, and grating.")
    c.drawString(ox + 10, 56.0, "Total payload with full liquid & fertilizer: 1,148.2 lbs | Suspended mass: ~1,465 lbs.")

def draw_sheet_s9(dc: DraftingCanvas, params: ProjectParameters, assembly: Dict[str, Any], stock_data: Dict[str, Any]):
    """Sheet S9: Stock Cutting Plan & Material Purchasing Requirements"""
    dc.draw_border_and_title_block("S9", "STOCK CUTTING PLAN & PURCHASING OPTIMIZATION", 9, 9)
    c = dc.c
    
    ox = 55.0
    oy = 520.0
    
    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColor(colors.HexColor("#001D3D"))
    c.drawString(ox, oy, "STOCK CUTTING PLAN - 1D LINEAR NESTING DIAGRAMS")
    
    stock_plan = stock_data.get("stock_plan", [])
    y = oy - 22
    bar_w = 440.0
    
    for i, stick in enumerate(stock_plan):
        if y < 140:
            break
            
        stk_id = stick.get("stick_id", f"STK-{i+1:02d}")
        sec = stick.get("section", "")
        stk_len = stick.get("stock_length", 240.0)
        parts = stick.get("parts", [])
        eff = stick.get("efficiency_pct", 0.0)
        scrap = stick.get("scrap_remaining", 0.0)
        
        c.setFont("Helvetica-Bold", 6.5)
        c.setFillColor(colors.HexColor("#0D1B2A"))
        c.drawString(ox, y, f"{stk_id}: {sec} - {fraction_str(stk_len)} ({stk_len/12:.0f}-ft Stock) | Yield: {eff:.1f}% | Remnant Scrap: {fraction_str(scrap)}")
        
        y -= 15
        # Full stock bar
        c.setFillColor(colors.HexColor("#E9ECEF"))
        c.setStrokeColor(colors.black)
        c.setLineWidth(1.0)
        c.rect(ox, y, bar_w, 13, fill=1, stroke=1)
        
        # Nested parts inside bar
        cur_px = ox
        for p in parts:
            p_len = p.get("length", 0.0)
            part_bar_w = (p_len / stk_len) * bar_w
            c.setFillColor(colors.HexColor("#A2D2FF"))
            c.setStrokeColor(colors.HexColor("#0077B6"))
            c.rect(cur_px, y, part_bar_w, 13, fill=1, stroke=1)
            
            # Smart text formatting: only print what fits
            c.setFillColor(colors.HexColor("#03045E"))
            c.setFont("Helvetica-Bold", 5.0)
            if part_bar_w >= 36:
                c.drawCentredString(cur_px + part_bar_w/2, y + 4, f"{p.get('piece_mark', '')} ({fraction_str(p_len)})")
            elif part_bar_w >= 18:
                c.drawCentredString(cur_px + part_bar_w/2, y + 4, p.get('piece_mark', ''))
            cur_px += part_bar_w
            
        y -= 22
        
    # Purchasing Summary Box (Cleanly on left bottom, zero overlap with title block)
    purch_y = 45.0
    c.setFillColor(colors.HexColor("#F8F9FA"))
    c.setStrokeColor(colors.HexColor("#003566"))
    c.rect(ox, purch_y, 410.0, 75.0, fill=1, stroke=1)
    c.setFont("Helvetica-Bold", 7.0)
    c.setFillColor(colors.HexColor("#003566"))
    c.drawString(ox + 8, purch_y + 63, "MATERIAL PURCHASING REQUIREMENTS (RAW STEEL ORDER LIST)")
    
    py = purch_y + 50
    c.setFont("Helvetica", 6.0)
    c.setFillColor(colors.black)
    for prow in stock_data.get("purchase_list", [])[:6]:
        c.drawString(ox + 8, py, f"- {prow.get('quantity')} Stick(s) {prow.get('section')} x {prow.get('stick_length')/12:.0f}-FT ({prow.get('grade')}) - Total: {prow.get('total_purchased_weight')} lb")
        py -= 9

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
