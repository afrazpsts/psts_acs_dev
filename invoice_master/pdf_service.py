from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.lib.units import mm
import urllib.request
from io import BytesIO
from datetime import datetime
import json
import re
from typing import Dict, Any, Optional
from common.logger import log as write_to_server_log

PRIMARY      = colors.HexColor('#0B6CC2')   
PRIMARY_LITE = colors.HexColor('#EFF6FF')   
PRIMARY_BDR  = colors.HexColor('#BFDBFE')   
DARK         = colors.HexColor('#1F2937')   
BODY         = colors.HexColor('#374151')   
MUTED        = colors.HexColor('#9CA3AF')   
HAIRLINE     = colors.HexColor('#F3F4F6')   
WHITE        = colors.white

W, H  = A4
ML    = 45
MR    = 45
CW    = W - ML - MR
RX    = ML + CW

COL_HRS_R  = ML + CW * 0.675
COL_RATE_R = ML + CW * 0.825
COL_AMT_R  = RX



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
    if s is None:
        s = ''
    cv.drawString(x, y, str(s))
    cv.restoreState()


def text_right(cv, rx, y, s, font='Helvetica', size=8, color=BODY):
    cv.saveState()
    cv.setFont(font, size)
    cv.setFillColor(color)
    if s is None:
        s = ''
    cv.drawRightString(rx, y, str(s))
    cv.restoreState()


def text_center(cv, x, y, s, font='Helvetica', size=8, color=BODY):
    cv.saveState()
    cv.setFont(font, size)
    cv.setFillColor(color)
    if s is None:
        s = ''
    cv.drawCentredString(x, y, str(s))
    cv.restoreState()


def lbl(cv, x, y, s):
    if s is None:
        s = ''
    text_left(cv, x, y, s.upper(), font='Helvetica-Bold', size=6.5, color=MUTED)


def bold(cv, x, y, s, size=9, color=BODY):
    if s is None:
        s = ''
    text_left(cv, x, y, s, font='Helvetica-Bold', size=size, color=color)


def bold_r(cv, rx, y, s, size=9, color=BODY):
    if s is None:
        s = ''
    text_right(cv, rx, y, s, font='Helvetica-Bold', size=size, color=color)


def format_currency(amount):
    """Format amount as currency"""
    try:
        if amount is None:
            return "$0.00"
        return f"${float(amount):,.2f}"
    except:
        return f"${amount}"


def parse_extra_amount(extra_amount):
    """Parse extra_amount from JSON string"""
    if not extra_amount:
        return []
    if isinstance(extra_amount, list):
        return extra_amount
    if isinstance(extra_amount, str):
        try:
            return json.loads(extra_amount)
        except:
            return []
    return []


def get_extra_amount_total(extra_amount):
    """Calculate total from extra_amount list"""
    extra_list = parse_extra_amount(extra_amount)
    total = 0
    for item in extra_list:
        if isinstance(item, dict):
            total += float(item.get('amount', 0))
        elif isinstance(item, (int, float)):
            total += float(item)
    return total


def format_date(date_str):
    """Convert date from YYYY-MM-DD to DD-MM-YYYY format"""
    if not date_str:
        return ""
    try:
        if 'T' in date_str:
            date_str = date_str.split('T')[0]
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        return dt.strftime('%d-%m-%Y')
    except:
        return str(date_str)


def strip_html_tags(html_string):
    """Remove HTML tags from string and convert to plain text"""
    if not html_string:
        return ""
    clean = re.compile('<.*?>')
    text = re.sub(clean, '', html_string)
    text = text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
    text = text.replace('&quot;', '"').replace('&apos;', "'")
    text = ' '.join(text.split())
    return text


def safe_str(value):
    """Convert any value to safe string, handling None"""
    if value is None:
        return ''
    return str(value)



def build_invoice_from_data(invoice_data: Dict[str, Any], output_buffer=None):
    """
    Generate invoice PDF from database data
    """
    if output_buffer is None:
        output_buffer = BytesIO()
    
    cv = canvas.Canvas(output_buffer, pagesize=A4)
    cv.setTitle(f"Invoice {invoice_data.get('invoice_number', 'Unknown')}")
    
    invoice_number = safe_str(invoice_data.get('invoice_number', 'INV-0001'))
    resident = invoice_data.get('resident', {})
    resident_name = f"{safe_str(resident.get('first_name', ''))} {safe_str(resident.get('last_name', ''))}".strip() or "Unknown Resident"
    
    # Get address from building/level/unit
    building_name = safe_str(invoice_data.get('building_name', ''))
    level_name = safe_str(invoice_data.get('level_name', ''))
    unit_number = safe_str(invoice_data.get('unit_number', ''))
    
    address_lines = []
    if unit_number:
        address_lines.append(f"Unit #{unit_number}")
    if building_name:
        address_lines.append(building_name)
    
    # Get vehicle items
    vehicle_items = invoice_data.get('vehicle_items', [])
    
    invoice_date = format_date(invoice_data.get('invoice_date', ''))
    due_date = format_date(invoice_data.get('due_date', ''))
    
    period = safe_str(invoice_data.get('period', datetime.now().strftime('%b %Y')))
    
    sub_total = float(invoice_data.get('sub_total', 0) or 0)
    gst = float(invoice_data.get('gst', 0) or 0)
    total_amount = float(invoice_data.get('total_amount', 0) or 0)
    discount = float(invoice_data.get('discount', 0) or 0)
    
    terms_and_conditions = invoice_data.get('terms_and_conditions', '')
    terms_text = strip_html_tags(terms_and_conditions)
    
    extra_amount_total = 0
    all_extra_charges = []
    for item in vehicle_items:
        extra_amount_value = item.get('extra_amount', 0)
        if extra_amount_value:
            if isinstance(extra_amount_value, str):
                try:
                    extra_list = json.loads(extra_amount_value)
                    for extra in extra_list:
                        if isinstance(extra, dict):
                            extra_amount_total += float(extra.get('amount', 0))
                            all_extra_charges.append(extra)
                        elif isinstance(extra, (int, float)):
                            extra_amount_total += float(extra)
                            all_extra_charges.append({"reason": "Extra charge", "amount": float(extra)})
                except:
                    pass
            elif isinstance(extra_amount_value, (int, float)):
                extra_amount_total += float(extra_amount_value)
                all_extra_charges.append({"reason": "Extra charge", "amount": float(extra_amount_value)})
            elif isinstance(extra_amount_value, list):
                for extra in extra_amount_value:
                    if isinstance(extra, dict):
                        extra_amount_total += float(extra.get('amount', 0))
                        all_extra_charges.append(extra)
                    elif isinstance(extra, (int, float)):
                        extra_amount_total += float(extra)
                        all_extra_charges.append({"reason": "Extra charge", "amount": float(extra)})
    
    status = safe_str(invoice_data.get('status', 'DRAFT'))
    is_paid = status.upper() == 'PAID'
    status_display = 'Paid' if is_paid else 'Pending'
    status_color = colors.HexColor('#10B981') if is_paid else colors.HexColor('#f59e0b')
    
    current_datetime = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
    
    logo_url = 'https://sykon.mjt.lu/img2/sykon/7366a578-81f7-4f8c-80cd-f16195af2130/content'
    

    HTOP = H - 48
    
    bold(cv, ML, HTOP, 'INVOICE', size=36, color=DARK)
    lbl(cv, ML, HTOP - 20, 'Invoice Number')
    bold(cv, ML, HTOP - 33, invoice_number, size=13, color=DARK)
    
    text_left(cv, ML, HTOP - 48, f"Generated: {current_datetime}", size=7, color=MUTED)
    
    # Right — Logo
    addr_y_offset = 18
    try:
        with urllib.request.urlopen(logo_url, timeout=10) as response:
            logo_data = response.read()
        logo_buffer = BytesIO(logo_data)
        logo = ImageReader(logo_buffer)
        
        logo_width = 100
        logo_height = 55
        logo_x = RX - logo_width
        logo_y = HTOP - 20
        
        cv.drawImage(logo, logo_x, logo_y, width=logo_width, height=logo_height, mask='auto')
        addr_y_offset = logo_height - 15
    except Exception as e:
        write_to_server_log(f"Warning: Could not load logo - {e}")
        bold_r(cv, RX, HTOP, 'Property Management', size=17, color=PRIMARY)
    
    company_lines = ["Powersoft Techno Solutions Pte Ltd", "15-01, Sim Lim Tower, 10 Jln Besar, Singapore 208787"]
    ay = HTOP - addr_y_offset - 8
    for line in company_lines:
        text_right(cv, RX, ay, safe_str(line), size=7, color=MUTED)
        ay -= 10
    
    DIV1_Y = HTOP - 58 - (addr_y_offset if 'logo' in locals() else 0) - 15
    hline(cv, ML, RX, DIV1_Y, color=HAIRLINE, lw=0.8)
    
    S2TOP = DIV1_Y - 14
    LEFT_W = CW * 0.575
    GAP = 14
    RIGHT_X = ML + LEFT_W + GAP
    RIGHT_W = RX - RIGHT_X
    META_H = 134
    META_BOT = S2TOP - META_H
    
    # Recipient label
    lbl(cv, ML, S2TOP, 'Recipient')
    
    # Blue left-accent bar
    rect(cv, ML, S2TOP - 8 - 56, 3, 56, PRIMARY)
    
    # Name & address
    bold(cv, ML + 12, S2TOP - 18, resident_name, size=13, color=DARK)
    ry2 = S2TOP - 32
    for ln in address_lines:
        text_left(cv, ML + 12, ry2, safe_str(ln), size=8, color=MUTED)
        ry2 -= 11
    
    VEH_SEP = ry2 - 5
    hline(cv, ML, ML + LEFT_W, VEH_SEP, color=HAIRLINE)
    VEH_Y = VEH_SEP - 14
    lbl(cv, ML, VEH_Y, 'Vehicle Plate')
    lbl(cv, ML + 105, VEH_Y, 'Vehicle Type')
    
    vehicle_number = safe_str(vehicle_items[0].get('vehicle_number', 'N/A')) if vehicle_items else 'N/A'
    vehicle_type = safe_str(vehicle_items[0].get('vehicle_type_name', 'N/A')) if vehicle_items else 'N/A'
    
    bold(cv, ML, VEH_Y - 13, vehicle_number, size=9, color=DARK)
    bold(cv, ML + 105, VEH_Y - 13, vehicle_type, size=9, color=DARK)
    
    # Meta box background
    rect(cv, RIGHT_X, META_BOT, RIGHT_W, META_H, PRIMARY_LITE)
    
    # Meta rows
    mr_y = S2TOP - 16
    meta_data = [
        ('Issue Date', invoice_date),
        ('Due Date', due_date),
        ('Period', period)
    ]
    for lbl_txt, val in meta_data:
        lbl(cv, RIGHT_X + 12, mr_y, lbl_txt)
        bold_r(cv, RX - 12, mr_y, safe_str(val), size=8, color=DARK)
        mr_y -= 24
    
    # Status badge
    lbl(cv, RIGHT_X + 12, mr_y, 'Status')
    PW, PH = 60, 15
    PX = RX - 12 - PW
    PY_badge = mr_y - 5
    rect(cv, PX, PY_badge, PW, PH, status_color)
    cv.saveState()
    cv.setFont('Helvetica-Bold', 6.5)
    cv.setFillColor(WHITE)
    cv.drawCentredString(PX + PW / 2, PY_badge + 4.5, status_display)
    cv.restoreState()
    

    TBL_TOP = META_BOT - 20
    HDR_Y = TBL_TOP
    
    # Header top line
    hline(cv, ML, RX, HDR_Y + 13, color=DARK, lw=1.5)
    
    COL_SNO_X = ML + 25           
    COL_VEHICLE_PLATE_X = ML + 55 
    COL_VEHICLE_TYPE_X = ML + 165 
    COL_QTY_X = ML + 265          
    COL_RATE_X = ML + 315        
    COL_AMOUNT_X = RX - 10        
    
    text_left(cv, ML, HDR_Y, 'S.NO', font='Helvetica-Bold', size=7, color=MUTED)
    text_left(cv, COL_VEHICLE_PLATE_X, HDR_Y, 'Vehicle Plate', font='Helvetica-Bold', size=7, color=MUTED)
    text_left(cv, COL_VEHICLE_TYPE_X, HDR_Y, 'Vehicle Type', font='Helvetica-Bold', size=7, color=MUTED)
    text_right(cv, COL_QTY_X, HDR_Y, 'QTY', font='Helvetica-Bold', size=7, color=MUTED)
    text_right(cv, COL_RATE_X, HDR_Y, 'RATE', font='Helvetica-Bold', size=7, color=MUTED)
    text_right(cv, COL_AMOUNT_X, HDR_Y, 'AMOUNT', font='Helvetica-Bold', size=7, color=MUTED)
    
    items = []
    sno = 1
    
    for item in vehicle_items:
        vehicle_num = safe_str(item.get('vehicle_number', 'N/A'))
        vehicle_type_name = safe_str(item.get('vehicle_type_name', 'Parking'))
        item_sub_total = float(item.get('sub_total', 0) or 0)
        
        item_extra_list = []
        extra_amount_val = item.get('extra_amount', 0)
        
        if extra_amount_val:
            if isinstance(extra_amount_val, str):
                try:
                    extra_list = json.loads(extra_amount_val)
                    for extra in extra_list:
                        if isinstance(extra, dict):
                            item_extra_list.append(extra)
                except:
                    pass
            elif isinstance(extra_amount_val, list):
                for extra in extra_amount_val:
                    if isinstance(extra, dict):
                        item_extra_list.append(extra)
        
        items.append({
            'sno': sno,
            'vehicle_plate': vehicle_num,
            'vehicle_type': vehicle_type_name,
            'qty': '1',
            'rate': format_currency(item_sub_total),
            'amount': format_currency(item_sub_total),
            'is_extra': False
        })
        sno += 1
        
        for extra in item_extra_list:
            extra_amount_val = float(extra.get('amount', 0))
            extra_reason = safe_str(extra.get('reason', 'Extra charge'))
            items.append({
                'sno': sno,
                'vehicle_plate': '-',
                'vehicle_type': extra_reason,
                'qty': '1',
                'rate': format_currency(extra_amount_val),
                'amount': format_currency(extra_amount_val),
                'is_extra': True
            })
            sno += 1
    
    if not items:
        items.append({
            'sno': '1',
            'vehicle_plate': 'N/A',
            'vehicle_type': 'N/A',
            'qty': '-',
            'rate': '-',
            'amount': '$0.00',
            'is_extra': False
        })
    
    ROW_H = 28
    ITEM_Y = HDR_Y - 18
    max_rows = 15
    
    for idx, item in enumerate(items[:max_rows]):
        row_center_y = ITEM_Y - (ROW_H / 2) + 4
        
        text_left(cv, ML, row_center_y, str(item['sno']), size=9, color=BODY)
        
        if item['is_extra']:
            text_left(cv, COL_VEHICLE_PLATE_X, row_center_y, '-', size=9, color=MUTED)
        else:
            bold(cv, COL_VEHICLE_PLATE_X, row_center_y, item['vehicle_plate'], size=9, color=DARK)
        
        vehicle_type_value = item.get('vehicle_type', '')
        if vehicle_type_value is None:
            vehicle_type_value = ''
        if item['is_extra']:
            text_left(cv, COL_VEHICLE_TYPE_X, row_center_y, safe_str(vehicle_type_value), size=9, color=MUTED)
        else:
            text_left(cv, COL_VEHICLE_TYPE_X, row_center_y, safe_str(vehicle_type_value), size=9, color=BODY)
        
        # QTY column - Right aligned
        if item['qty'] == '-':
            text_right(cv, COL_QTY_X, row_center_y, item['qty'], size=9, color=BODY)
        else:
            text_right(cv, COL_QTY_X, row_center_y, item['qty'], size=9, color=BODY)
        
        if item['is_extra']:
            text_right(cv, COL_RATE_X, row_center_y, item['rate'], size=9, color=MUTED)
        else:
            text_right(cv, COL_RATE_X, row_center_y, item['rate'], size=9, color=BODY)
        
        if item['is_extra']:
            text_right(cv, COL_AMOUNT_X, row_center_y, item['amount'], size=9, color=MUTED)
        else:
            bold_r(cv, COL_AMOUNT_X, row_center_y, item['amount'], size=9, color=PRIMARY)
        
        if idx < len(items) - 1:
            hline(cv, ML, RX, ITEM_Y - ROW_H + 4, color=HAIRLINE)
        
        ITEM_Y -= ROW_H
    
    TOT_X = ML + CW * 0.65
    TOT_Y = ITEM_Y - 15
    
    # Subtotal
    lbl(cv, TOT_X, TOT_Y, 'Subtotal')
    bold_r(cv, RX, TOT_Y, format_currency(sub_total), size=10, color=DARK)
    hline(cv, TOT_X, RX, TOT_Y - 8, color=HAIRLINE)
    TOT_Y -= 24
    
    # Extra Charges (if any)
    if extra_amount_total > 0:
        lbl(cv, TOT_X, TOT_Y, 'Extra Charges')
        bold_r(cv, RX, TOT_Y, format_currency(extra_amount_total), size=10, color=DARK)
        hline(cv, TOT_X, RX, TOT_Y - 8, color=HAIRLINE)
        TOT_Y -= 24
    
    if discount > 0:
        lbl(cv, TOT_X, TOT_Y, 'Discount')
        bold_r(cv, RX, TOT_Y, f"-{format_currency(discount)}", size=10, color=DARK)
        hline(cv, TOT_X, RX, TOT_Y - 8, color=HAIRLINE)
        TOT_Y -= 24
    
    # GST
    lbl(cv, TOT_X, TOT_Y, f'GST (9%)')
    bold_r(cv, RX, TOT_Y, format_currency(gst), size=10, color=DARK)
    hline(cv, TOT_X, RX, TOT_Y - 8, color=HAIRLINE)
    
    # Total Due banner
    TOT_Y -= 28
    BAN_H = 50
    BAN_BOT = TOT_Y - BAN_H
    
    rect(cv, ML, BAN_BOT, CW, BAN_H, PRIMARY_LITE, PRIMARY_BDR, 1.0)
    
    # Calculate vertical center for the container
    center_y = BAN_BOT + (BAN_H / 2)
    
    # TOTAL DUE text
    cv.saveState()
    cv.setFont('Helvetica-Bold', 11)
    cv.setFillColor(DARK)
    cv.drawString(ML + 20, center_y - 4, 'TOTAL DUE')
    
    # Amount
    cv.setFont('Helvetica-Bold', 24)
    cv.setFillColor(PRIMARY)
    cv.drawRightString(RX - 20, center_y - 6, format_currency(total_amount))
    cv.restoreState()

    if terms_text:
        TERMS_Y = BAN_BOT - 20
        lbl(cv, ML, TERMS_Y, 'Terms & Conditions')
        
        terms_lines = []
        words = terms_text.split()
        current_line = ""
        for word in words:
            test_line = current_line + " " + word if current_line else word
            if len(test_line) > 60:
                terms_lines.append(current_line)
                current_line = word
            else:
                current_line = test_line
        if current_line:
            terms_lines.append(current_line)
        
        terms_y = TERMS_Y - 15
        for line in terms_lines:
            text_left(cv, ML, terms_y, safe_str(line), size=7.5, color=MUTED)
            terms_y -= 12
    

    FY = 30
    hline(cv, ML, RX, FY + 22, color=HAIRLINE, lw=0.8)
    text_left(cv, ML, FY + 12,
              'PSTS Access Control',
              font='Helvetica-Bold', size=7, color=MUTED)
    text_left(cv, ML, FY + 2,
              'UEN: 202600123A | GST Registered',
              font='Helvetica-Bold', size=7, color=MUTED)
    text_right(cv, RX, FY + 12, 'Contact: support@psts.com | Tel: +65 1234 5678',
               font='Helvetica-Bold', size=7, color=MUTED)
    
    cv.save()
    output_buffer.seek(0)
    return output_buffer