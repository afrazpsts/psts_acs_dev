from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta
import uuid
from cryptography.fernet import Fernet
import random
from fastapi.responses import StreamingResponse
import qrcode
import socket

import io
from cryptography.fernet import Fernet
import string
import requests
from utils.security import shorten_url_with_tinyurl,fernet
from requests.auth import HTTPDigestAuth
import urllib3
from utils.mailjet_service import send_qr_email  
import json
from utils.sms_service import send_sms

from DB.db import get_db
from utils.security import decrypt_password
from utils.common_function import generate_card_number as generate_card_no,generate_visitor_id,generate_token,BASE_URL,generate_unique_qr_token

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

router = APIRouter()


# def generate_unique_qr_token(db: Session, length: int = 8) -> str:
#     """Generate a unique QR token for adoc visitors."""
#     while True:
#         token = generate_token(length)
#         exists = db.execute(
#             text("SELECT 1 FROM adoc_visitor WHERE qr_token = :qr_token LIMIT 1"),
#             {"qr_token": token}
#         ).scalar()
#         if not exists:
#             return token

# def generate_visitor_id() -> str:
#     return uuid.uuid4().hex

# def generate_card_no(length: int = 20) -> str:
#     chars = string.ascii_uppercase + string.digits
#     return ''.join(random.choices(chars, k=length))

def create_visitor_profile(device_ip, username, password,
                           visitor_id, name, gender, valid_from, valid_to):
    """
    Create visitor profile on the device
    """
    url = f"http://{device_ip}/ISAPI/AccessControl/UserInfo/Record?format=json"
    
    # Ensure gender is provided
    if not gender:
        gender = "unknown"
    
    payload = {
        "UserInfo": {
            "employeeNo": visitor_id,
            "name": name,
            "userType": "visitor",
            "Valid": {
                "enable": True,
                "beginTime": valid_from,
                "endTime": valid_to,
                "timeType": "local"
            },
            "doorRight": "1",
            "RightPlan": [{"doorNo": 1, "planTemplateNo": "1"}],
            "gender": gender,
            "localUIRight": False
        }
    }
    
    try:
        res = requests.post(url, auth=HTTPDigestAuth(username, password),
                            json=payload, verify=False, timeout=30)
        print(f"Profile upload response: {res.status_code} - {res.text}")
        return res.status_code == 200, res.text
    except requests.exceptions.RequestException as e:
        print(f"Request error in create_visitor_profile: {str(e)}")
        return False, str(e)

def upload_qr_card(device_ip, username, password,
                   visitor_id, card_no, valid_from, valid_to):
    url = f"http://{device_ip}/ISAPI/AccessControl/CardInfo/Record?format=json"

    payload = {
        "CardInfo": {
            "employeeNo": visitor_id,
            "cardNo": card_no,
            "cardType": "normalCard",
            "userType": "visitor",
            "status": "active",
            "doorRight": "10",
            "valid": {
                "enable": True,
                "beginTime": valid_from,
                "endTime": valid_to
            }
        }
    }

    res = requests.post(url, auth=HTTPDigestAuth(username, password),
                        json=payload, verify=False)
    return res.status_code == 200, res.text

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


@router.post("/create_adoc_visitor")
def create_adoc_visitor(payload: dict, db: Session = Depends(get_db)):
    try:
        print("Received Payload:", payload) 
        building_id = payload["building_id"]

        assign = db.execute(text("""
            SELECT device_id FROM assign_devices WHERE building_id = :building_id
        """), {"building_id": building_id}).mappings().first()
        if not assign:
            raise HTTPException(status_code=404, detail="No device assigned.")

        device = db.execute(text("""
            SELECT ip, user_name, password FROM camera_devices WHERE id = :device_id
        """), {"device_id": assign["device_id"]}).mappings().first()
        if not device:
            raise HTTPException(status_code=404, detail="Device not found.")

        visitor_id = generate_visitor_id()
        qr_token = generate_unique_qr_token(db)
        card_no = generate_card_no()
        valid_from = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        valid_to = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
        
        # Get gender from payload or use default
        gender = payload.get("gender", "unknown")

        success_profile, profile_response = create_visitor_profile(
            device["ip"], 
            device["user_name"], 
            decrypt_password(device["password"]),
            visitor_id, 
            payload["name"], 
            gender,  # Added gender parameter
            valid_from, 
            valid_to
        )
        
        if not success_profile:
            raise HTTPException(status_code=400, detail=f"Failed to upload visitor profile: {profile_response}")
            
        success_card, card_response = upload_qr_card(
            device["ip"], 
            device["user_name"], 
            decrypt_password(device["password"]),
            visitor_id, 
            card_no, 
            valid_from, 
            valid_to
        )

        if not success_card:
            raise HTTPException(status_code=400, detail=f"Failed to upload QR card: {card_response}")

        db.execute(text("""
            INSERT INTO adoc_visitor (
                adoc_visitor_id, name, email, phone, building_id, unit_id, level_id, purpose_visit,
                card_no, valid, qr_token, created_at, updated_at
            ) VALUES (
                :adoc_visitor_id, :name, :email, :phone, :building_id, :unit_id, :level_id, :purpose_visit,
                :card_no, :valid, :qr_token, NOW(), NOW()
            )
        """), {
            "adoc_visitor_id": visitor_id,  
            "name": payload["name"],
            "email": payload.get("email"),
            "phone": payload.get("phone"),
            "building_id": building_id,
            "unit_id": payload["unit_id"],
            "level_id": payload["level_id"],
            "purpose_visit": payload.get("purpose_visit"), 
            "card_no": card_no,
            "valid": json.dumps({"beginTime": valid_from, "endTime": valid_to}),
            "qr_token": qr_token
        })

        db.commit()

        qr_url_long = f"{BASE_URL}/view_qr/{qr_token}"
        qr_url = shorten_url_with_tinyurl(qr_url_long)

        if payload.get("email"):
            send_qr_email(
                email=payload["email"],
                name=payload["name"],
                building=payload.get("building_name", "Building"),
                card_no=card_no,
                valid_from=valid_from,
                valid_to=valid_to,
                qr_url=qr_url
            )

        if payload.get("phone"):
            sms_text = (
                f"Hi {payload['name']},\n"
                f"You've been granted visitor access to {payload.get('building_name', 'the building')}.\n"
                f"Click the link to view your QR."
            )
            send_sms(to_number=payload["phone"], message=sms_text + f"\n{qr_url}") 

        return {
            "status": 200,
            "message": "Adoc visitor created and QR sent.",
            "data": {
                "visitor_id": visitor_id,
                "name": payload["name"],
                "qr_token": qr_token,
                "qr_url": qr_url_long,
                "valid_from": valid_from,
                "valid_to": valid_to
            }
        }

    except HTTPException:  
        raise
    except Exception as e:
        print(f"Error in create_adoc_visitor: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.get("/view_qr_image/{encrypted_card_no}")
def view_qr(encrypted_card_no: str):
    try:
        decrypted_card_no = fernet.decrypt(encrypted_card_no.encode()).decode()
        qr = qrcode.make(decrypted_card_no)
        buf = io.BytesIO()
        qr.save(buf, format='PNG')
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or expired QR code.")

    
@router.get("/list_adoc_visitors")
def list_adoc_visitors(db: Session = Depends(get_db)):
    try:
        query = text("""
            SELECT 
                av.id,
                av.name,
                av.phone,
                av.email,
                av.card_no,
                av.valid,
                av.created_at,
                av.updated_at,

                pb.id AS building_id,
                pb.building_name,

                bl.id AS level_id,
                bl.level,

                bu.id AS unit_id,
                bu.unit_no

            FROM adoc_visitor av
            LEFT JOIN property_building pb ON av.building_id = pb.id
            LEFT JOIN building_level bl ON av.level_id = bl.id
            LEFT JOIN building_units bu ON av.unit_id = bu.id

            ORDER BY av.created_at DESC
        """)
        result = db.execute(query).mappings().all()

        return {
            "status": 200,
            "message": "Adoc visitors fetched successfully.",
            "data": result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    
# DEVICE_IP = "192.168.1.232"
# USERNAME = "admin"
# PASSWORD = "Psts@123"


    
