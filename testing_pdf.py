"""
Invoice PDF generator — ReportLab canvas-based, A4 single page.
Primary color: Blue (#0B6CC2)
Run: python generate_invoice.py  →  creates invoice.pdf
"""
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
import urllib.request
from io import BytesIO

# ── Palette ───────────────────────────────────────────────────────────────────
PRIMARY      = colors.HexColor('#0B6CC2')   # blue
PRIMARY_LITE = colors.HexColor('#EFF6FF')   # blue-50
PRIMARY_BDR  = colors.HexColor('#BFDBFE')   # blue-100
DARK         = colors.HexColor('#1F2937')   # gray-800
BODY         = colors.HexColor('#374151')   # gray-700
MUTED        = colors.HexColor('#9CA3AF')   # gray-400
HAIRLINE     = colors.HexColor('#F3F4F6')   # gray-100
WHITE        = colors.white

# ── Page geometry ─────────────────────────────────────────────────────────────
W, H  = A4
ML    = 45
MR    = 45
CW    = W - ML - MR
RX    = ML + CW

# ── Table column right-edges ──────────────────────────────────────────────────
COL_HRS_R  = ML + CW * 0.675
COL_RATE_R = ML + CW * 0.825
COL_AMT_R  = RX


# ── Helpers ───────────────────────────────────────────────────────────────────

def rect(cv, x, y, w, h, fill, stroke_color=None, lw=0.5):
    cv.saveState()
    cv.setFillColor(fill)
    if stroke_color:
        cv.setStrokeColor(stroke_color)
        cv.setLineWidth(lw)
    cv.rect(x, y, w, h, fill=1, stroke=1 if stroke_color else 0)
    cv.restoreState()


def hline(cv, x1, x2, y, color=HAIRLINE, lw=0.5):
    cv.saveState()
    cv.setStrokeColor(color)
    cv.setLineWidth(lw)
    cv.line(x1, y, x2, y)
    cv.restoreState()


def text_left(cv, x, y, s, font='Helvetica', size=8, color=BODY):
    cv.saveState()
    cv.setFont(font, size)
    cv.setFillColor(color)
    cv.drawString(x, y, s)
    cv.restoreState()


def text_right(cv, rx, y, s, font='Helvetica', size=8, color=BODY):
    cv.saveState()
    cv.setFont(font, size)
    cv.setFillColor(color)
    cv.drawRightString(rx, y, s)
    cv.restoreState()


def text_center(cv, x, y, s, font='Helvetica', size=8, color=BODY):
    cv.saveState()
    cv.setFont(font, size)
    cv.setFillColor(color)
    cv.drawCentredString(x, y, s)
    cv.restoreState()


def lbl(cv, x, y, s):
    text_left(cv, x, y, s.upper(), font='Helvetica-Bold', size=6.5, color=MUTED)


def bold(cv, x, y, s, size=9, color=BODY):
    text_left(cv, x, y, s, font='Helvetica-Bold', size=size, color=color)


def bold_r(cv, rx, y, s, size=9, color=BODY):
    text_right(cv, rx, y, s, font='Helvetica-Bold', size=size, color=color)


# ── Build ─────────────────────────────────────────────────────────────────────

def build_invoice(out='invoice.pdf'):
    cv = canvas.Canvas(out, pagesize=A4)
    cv.setTitle('Invoice INV-SG-CP-2026-001')

    # ══════════════════════════════════════════════════════════════════════════
    # 1.  HEADER
    # ══════════════════════════════════════════════════════════════════════════
    HTOP = H - 48

    # Left — title + invoice number
    bold(cv, ML, HTOP, 'INVOICE', size=36, color=DARK)
    lbl(cv,  ML, HTOP - 20, 'Invoice Number')
    bold(cv, ML, HTOP - 33, 'INV-SG-CP-2026-001', size=13, color=DARK)

    # Right — Logo (replaces the company name text)
    try:
        # Download the logo from URL
        logo_url = 'https://sykon.mjt.lu/img2/sykon/7366a578-81f7-4f8c-80cd-f16195af2130/content'
        with urllib.request.urlopen(logo_url) as response:
            logo_data = response.read()
        logo_buffer = BytesIO(logo_data)
        logo = ImageReader(logo_buffer)
        
        # Logo dimensions - adjust as needed
        logo_width = 100
        logo_height = 55
        logo_x = RX - logo_width
        logo_y = HTOP - 20
        
        cv.drawImage(logo, logo_x, logo_y, width=logo_width, height=logo_height, mask='auto')
        
        # Adjust address position based on logo height
        addr_y_offset = logo_height - 15
    except Exception as e:
        # Fallback if logo fails to load
        print(f"Warning: Could not load logo - {e}")
        bold_r(cv, RX, HTOP, 'Lasuisee - II', size=17, color=PRIMARY)
        addr_y_offset = 18
    
    # Company address (adjusted position if logo is present)
    addr_lines = [
        
    ]
    ay = HTOP - addr_y_offset - 8
    for line in addr_lines:
        text_right(cv, RX, ay, line, size=7, color=MUTED)
        ay -= 10

    DIV1_Y = HTOP - 58 - (addr_y_offset if 'logo' in locals() else 0)
    hline(cv, ML, RX, DIV1_Y, color=HAIRLINE, lw=0.8)

    # ══════════════════════════════════════════════════════════════════════════
    # 2.  RECIPIENT  (left)  +  META BOX  (right)
    # ══════════════════════════════════════════════════════════════════════════
    S2TOP    = DIV1_Y - 14
    LEFT_W   = CW * 0.575
    GAP      = 14
    RIGHT_X  = ML + LEFT_W + GAP
    RIGHT_W  = RX - RIGHT_X
    META_H   = 134
    META_BOT = S2TOP - META_H

    # Recipient label
    lbl(cv, ML, S2TOP, 'Recipient')

    # Blue left-accent bar
    rect(cv, ML, S2TOP - 8 - 56, 3, 56, PRIMARY)

    # Name & address
    bold(cv, ML + 12, S2TOP - 18, 'John Tan', size=13, color=DARK)
    ry2 = S2TOP - 32
    for ln in ['Unit #08-123', 'Lasuisee II Condominium', 'Singapore 543210']:
        text_left(cv, ML + 12, ry2, ln, size=8, color=MUTED)
        ry2 -= 11

    # Vehicle / Lot
    VEH_SEP = ry2 - 5
    hline(cv, ML, ML + LEFT_W, VEH_SEP, color=HAIRLINE)
    VEH_Y = VEH_SEP - 14
    lbl(cv,  ML,       VEH_Y, 'Vehicle Plate')
    lbl(cv,  ML + 105, VEH_Y, 'Vehicle Type')
    bold(cv, ML,       VEH_Y - 13, 'SGX1234A',         size=9, color=DARK)
    bold(cv, ML + 105, VEH_Y - 13, 'B2 \u2013 Lot 145', size=9, color=DARK)

    # Meta box background
    rect(cv, RIGHT_X, META_BOT, RIGHT_W, META_H, PRIMARY_LITE)

    # Meta rows - without bottom lines
    mr_y = S2TOP - 16
    for i, (lbl_txt, val) in enumerate([
            ('Issue Date', '01 Feb 2026'),
            ('Due Date',   '15 Feb 2026'),
            ('Period',     'Jan 2026')]):
        lbl(cv, RIGHT_X + 12, mr_y, lbl_txt)
        bold_r(cv, RX - 12, mr_y, val, size=8, color=DARK)
        mr_y -= 24

    # Access + ACTIVE badge
    lbl(cv, RIGHT_X + 12, mr_y, 'Status')
    PW, PH = 44, 15
    PX = RX - 12 - PW
    PY_badge = mr_y - 5
    rect(cv, PX, PY_badge, PW, PH, PRIMARY)
    cv.saveState()
    cv.setFont('Helvetica-Bold', 6.5)
    cv.setFillColor(WHITE)
    cv.drawCentredString(PX + PW / 2, PY_badge + 4.5, 'Paid')
    cv.restoreState()

    # ══════════════════════════════════════════════════════════════════════════
    # 3.  LINE ITEMS TABLE
    # ══════════════════════════════════════════════════════════════════════════
    TBL_TOP = META_BOT - 20
    HDR_Y   = TBL_TOP

    # Header top line
    hline(cv, ML, RX, HDR_Y + 13, color=DARK, lw=1.5)
    
    # Header labels
    lbl(cv,        ML,          HDR_Y, 'Service Description')
    text_right(cv, COL_HRS_R,  HDR_Y, 'HOURS',  font='Helvetica-Bold', size=6.5, color=MUTED)
    text_right(cv, COL_RATE_R, HDR_Y, 'RATE',   font='Helvetica-Bold', size=6.5, color=MUTED)
    text_right(cv, COL_AMT_R,  HDR_Y, 'AMOUNT', font='Helvetica-Bold', size=6.5, color=MUTED)

    items = [
        ('Season Parking Fee (Jan 2026)',
         'Monthly subscription for residential parking access via RFID/LPR.',
         '1', '$120.00', '$120.00'),
        ('Additional Vehicle Fee',
         'Administrative surcharge for second registered vehicle.',
         '1', '$80.00', '$80.00'),
        ('Late Payment Charges',
         'No outstanding arrears detected for previous billing cycles.',
         '-', '$0.00', '$0.00'),
    ]

    ROW_H  = 46
    ITEM_Y = HDR_Y - 18

    for name, desc, qty, rate, amt in items:
        bold(cv, ML, ITEM_Y, name, size=9, color=DARK)
        text_left(cv, ML, ITEM_Y - 13, desc, size=7.5, color=MUTED)
        MID = ITEM_Y - 7
        
        # Center align the quantity/dash in the HOURS column
        if qty == '-':
            text_center(cv, (COL_HRS_R + (COL_HRS_R - (COL_HRS_R - (CW * 0.5)))) / 1.5, MID, qty, size=9, color=BODY)
        else:
            text_right(cv, COL_HRS_R, MID, qty, size=9, color=BODY)
        
        text_right(cv, COL_RATE_R, MID, rate, size=9, color=BODY)
        bold_r(cv, COL_AMT_R, MID, amt, size=9, color=PRIMARY)
        hline(cv, ML, RX, ITEM_Y - ROW_H + 8, color=HAIRLINE)
        ITEM_Y -= ROW_H

    # ══════════════════════════════════════════════════════════════════════════
    # 4.  TOTALS
    # ══════════════════════════════════════════════════════════════════════════
    TOT_X = ML + CW * 0.65
    TOT_Y = ITEM_Y + ROW_H - 8 - 10

    # Add MORE spacing before totals (increased from 15 to 35)
    TOT_Y -= 35

    lbl(cv,    TOT_X, TOT_Y, 'Subtotal')
    bold_r(cv, RX,    TOT_Y, '$200.00', size=9, color=BODY)
    hline(cv, TOT_X, RX, TOT_Y - 8, color=HAIRLINE)

    TOT_Y -= 28  # Spacing between subtotal and GST
    lbl(cv,    TOT_X, TOT_Y, 'GST (9%)')
    bold_r(cv, RX,    TOT_Y, '$18.00', size=9, color=BODY)
    hline(cv, TOT_X, RX, TOT_Y - 8, color=HAIRLINE)

    # Total Due banner - Reduced height and text size
    TOT_Y  -= 28
    BAN_H   = 50  # Reduced from 70 to 50
    BAN_BOT = TOT_Y - BAN_H
    
    # Light blue background container
    rect(cv, ML, BAN_BOT, CW, BAN_H, PRIMARY_LITE, PRIMARY_BDR, 1.0)
    
    # Calculate vertical center for the container
    center_y = BAN_BOT + (BAN_H / 2)
    
    # TOTAL DUE text - left aligned (reduced font size)
    cv.saveState()
    cv.setFont('Helvetica-Bold', 11)  # Reduced from 14 to 11
    cv.setFillColor(DARK)
    cv.drawString(ML + 20, center_y - 4, 'TOTAL DUE')
    
    # Amount - right aligned (reduced font size)
    cv.setFont('Helvetica-Bold', 24)  # Reduced from 32 to 24
    cv.setFillColor(PRIMARY)
    cv.drawRightString(RX - 20, center_y - 6, '$218.00')
    cv.restoreState()

    # ══════════════════════════════════════════════════════════════════════════
    # 5.  FOOTER
    # ══════════════════════════════════════════════════════════════════════════
    FY = 30
    hline(cv, ML, RX, FY + 22, color=HAIRLINE, lw=0.8)
    text_left(cv,  ML, FY + 12,
              'Green Residency Management Corporation (MCST 5678)',
              font='Helvetica-Bold', size=7, color=MUTED)
    text_left(cv,  ML, FY + 2,
              'UEN: 202600123A | GST Registered',
              font='Helvetica-Bold', size=7, color=MUTED)
    text_right(cv, RX, FY + 12, 'Contact: support@psts.com | Tel: +971 4 123 4567',
               font='Helvetica-Bold', size=7, color=MUTED)

    cv.save()
    print(f'Saved -> {out}')


if __name__ == '__main__':
    build_invoice('invoice.pdf')