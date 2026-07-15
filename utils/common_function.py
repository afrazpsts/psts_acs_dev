import random
import string
import uuid
import urllib.request

from sqlmodel import Session, text 
from common.logger import log
from datetime import datetime

 

BASE_URL = "http://192.168.1.13:8000"


in_value = ["Entry Barrier", "Entry", "InGate"]
out_value = ["Exit Barrier", "Exit", "OutGate"]

CONFIG_ACCESS_UUID = "40d95dbef62e45f39237e13289942ae9"

def validate_config_uuid(uuid_param: str) -> bool:
    """Return True if the supplied UUID matches the config access UUID."""
    return uuid_param == CONFIG_ACCESS_UUID

def generate_token(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def generate_visitor_id() -> str:
    return uuid.uuid4().hex


def generate_card_number(length: int = 20) -> str:
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=length))

def generate_unique_qr_token(db: Session, length: int = 8) -> str:
    """Generate a unique QR token across adoc_visitor and invite_visitor."""
    while True:
        token = generate_token(length)
        
        # Check in adoc_visitor
        exists_in_adoc = db.execute(text("""
            SELECT 1 FROM adoc_visitor WHERE qr_token = :qr_token LIMIT 1
        """), {"qr_token": token}).scalar()
        
        if exists_in_adoc:
            continue
            
        # Check in invite_visitor
        exists_in_invite = db.execute(text("""
            SELECT 1 FROM invite_visitor WHERE qr_token = :qr_token LIMIT 1
        """), {"qr_token": token}).scalar()
        
        if not exists_in_invite:
            return token
        
def generate_employee_no():
    return f"EMP{random.randint(100000, 999999)}"


def generate_otp():
    return str(random.randint(100000, 999999))

import sys
import os

def get_resource_path(relative_path: str) -> str:
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.getcwd()

    return os.path.join(base_path, relative_path)


def format_date(date_value):
    """Helper function to format date for PDF in DD-MM-YYYY format"""
    if date_value is None:
        return "N/A"
    if isinstance(date_value, datetime):
        return date_value.strftime("%d-%m-%Y")  
    if isinstance(date_value, str):
        try:
            dt = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
            return dt.strftime("%d-%m-%Y")  
        except:
            date_str = date_value.strip()
            
            if len(date_str) >= 10 and date_str[4] == '-' and date_str[7] == '-':
                try:
                    year = int(date_str[0:4])
                    month = int(date_str[5:7])
                    day = int(date_str[8:10])
                    dt = datetime(year, month, day)
                    return dt.strftime("%d-%m-%Y")
                except:
                    pass
            
            if len(date_str) >= 10 and date_str[2] == '-' and date_str[5] == '-':
                return date_str[:10]  
            
            return date_str[:10] if len(date_str) >= 10 else date_str
    return str(date_value)

    
def get_logo_url_prod():
    return "https://sykon.mjt.lu/img2/sykon/7366a578-81f7-4f8c-80cd-f16195af2130/content"


    
def format_date_ddmmyyyy(date_obj):
    if not date_obj:
        return None

    if isinstance(date_obj, str):
        try:
            date_obj = datetime.strptime(date_obj, "%Y-%m-%d").date()
        except:
            return date_obj  

    return date_obj.strftime("%d-%m-%Y")
