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

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

router = APIRouter()

def generate_visitor_id() -> str:
    return uuid.uuid4().hex

def generate_card_no(length: int = 20) -> str:
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=length))

def create_visitor_profile(device_ip, username, password,
                           visitor_id, name, valid_from, valid_to):
    url = f"http://{device_ip}/ISAPI/AccessControl/UserInfo/Record?format=json"
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
            "gender": "unknown",  
            "localUIRight": False
        }
    }

    res = requests.post(url, auth=HTTPDigestAuth(username, password),
                        json=payload, verify=False)
    return res.status_code == 200, res.text

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


@router.post("/create_self_visitor")
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
        card_no = generate_card_no()
        valid_from = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        valid_to = (datetime.now() + timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%S")

        success_profile, _ = create_visitor_profile(
            device["ip"], device["user_name"], decrypt_password(device["password"]),
            visitor_id, payload["name"], valid_from, valid_to
        )
        success_card, _ = upload_qr_card(
            device["ip"], device["user_name"], decrypt_password(device["password"]),
            visitor_id, card_no, valid_from, valid_to
        )

        if not (success_profile and success_card):
            raise HTTPException(status_code=400, detail="Failed to upload visitor profile/QR.")

        db.execute(text("""
    INSERT INTO adoc_visitor (
        adoc_visitor_id, name, email, phone, building_id, unit_id, level_id, purpose_visit,
        card_no, original_card_no, valid, created_at, updated_at
    ) VALUES (
        :adoc_visitor_id, :name, :email, :phone, :building_id, :unit_id, :level_id, :purpose_visit,
        :card_no, :original_card_no, :valid, NOW(), NOW()
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
    "original_card_no": card_no,
    "valid": json.dumps({"beginTime": valid_from, "endTime": valid_to}),
})

        db.commit()

        encrypted_card_no = fernet.encrypt(card_no.encode()).decode()
        # local_ip = get_local_ip()
        qr_url_long = f"http://192.168.1.94:9000/view_qr/{encrypted_card_no}"
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
                "valid_from": valid_from,
                "valid_to": valid_to
            }
        }

    except HTTPException:  
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    
@router.get("/view_qr/{encrypted_card_no}")
def view_qr(encrypted_card_no: str, db: Session = Depends(get_db)):
    try:
        decrypted_card_no = fernet.decrypt(encrypted_card_no.encode()).decode()

        visitor = db.execute(text("""
            SELECT adoc_visitor_id, building_id, valid, card_no
            FROM adoc_visitor 
            WHERE original_card_no = :card_no
        """), {"card_no": decrypted_card_no}).mappings().first()

        if not visitor:
            raise HTTPException(status_code=404, detail="QR not found or expired.")

        adoc_visitor_id = visitor["adoc_visitor_id"]
        building_id = visitor["building_id"]
        old_card_no = visitor["card_no"]
        valid_data = json.loads(visitor["valid"])
        begin_time = valid_data.get("beginTime")
        end_time = valid_data.get("endTime")

        print(f"QR Accessed for visitor: {adoc_visitor_id}")
        print(f"Valid From: {begin_time}")
        print(f"Valid To: {end_time}")
        print(f"Access Time: {datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}")

        device = db.execute(text("""
            SELECT ip, user_name, password 
            FROM camera_devices 
            WHERE building_id = :building_id
            LIMIT 1
        """), {"building_id": building_id}).mappings().first()

        if not device:
            raise HTTPException(status_code=404, detail="No device found for this building.")

        device_ip = device["ip"]
        username = device["user_name"]
        password = decrypt_password(device["password"])

        print(f"Device Found: {device_ip} | User: {username}")

        delete_url = f"https://{device_ip}/ISAPI/AccessControl/CardInfo/Delete?format=json"
        delete_payload = {
            "CardInfoDelCond": {
                "CardNoList": [{"cardNo": old_card_no}]
            }
        }

        delete_res = requests.put(
            delete_url,
            auth=HTTPDigestAuth(username, password),
            json=delete_payload,
            verify=False
        )
        print("Delete Response:", delete_res.status_code, delete_res.text)

        if delete_res.status_code != 200:
            print("Warning: Failed to delete old card on device (might not exist).")

        new_card_no = generate_card_no()
        print(f"Generated New Card No: {new_card_no}")

        create_url = f"https://{device_ip}/ISAPI/AccessControl/CardInfo/Record?format=json"
        create_payload = {
            "CardInfo": {
                "employeeNo": adoc_visitor_id,
                "cardNo": new_card_no,
                "cardType": "normalCard"
            }
        }

        create_res = requests.post(
            create_url,
            auth=HTTPDigestAuth(username, password),
            json=create_payload,
            verify=False
        )
        print("Device Create Response:", create_res.status_code, create_res.text)

        if create_res.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to create new card on device.")

        db.execute(text("""
            UPDATE adoc_visitor
            SET card_no = :new_card_no, updated_at = NOW()
            WHERE adoc_visitor_id = :adoc_visitor_id
        """), {"new_card_no": new_card_no, "adoc_visitor_id": adoc_visitor_id})
        db.commit()

        qr = qrcode.make(new_card_no)
        buf = io.BytesIO()
        qr.save(buf, format='PNG')
        buf.seek(0)

        return StreamingResponse(buf, media_type="image/png")

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error while updating card: {str(e)}")




    
# def person_from_device(employee_no: str, DEVICE_IP: str, USERNAME: str, PASSWORD: str):
#     url = f"https://{DEVICE_IP}/ISAPI/AccessControl/UserInfo/Delete?format=json"
#     payload = {
#         "UserInfoDelCond": {
#             "EmployeeNoList": [{"employeeNo": employee_no}]
#         }
#     }
#     headers = {"Content-Type": "application/json"}

#     print(f"\nPayload for Delete ({DEVICE_IP}):\n{json.dumps(payload, indent=2)}")

#     try:
#         response = requests.put(
#             url,
#             data=json.dumps(payload),
#             headers=headers,
#             auth=HTTPDigestAuth(USERNAME, PASSWORD),
#             verify=False
#         )

#         if response.ok:
#             return {
#                 "status": "success",
#                 "data": response.json(),
#                 "employee_no": employee_no
#             }
#         else:
#             try:
#                 error_data = response.json()
#             except Exception:
#                 error_data = response.text or "Unknown error"

#             return {
#                 "status": "error",
#                 "error": error_data,
#                 "status_code": response.status_code
#             }

#     except Exception as e:
#         return {
#             "status": "error",
#             "error": str(e)
#         }

# @router.delete("/delete_adoc_visitor/{adoc_visitor_id}")
# def delete_adoc_visitor(adoc_visitor_id: str, db: Session = Depends(get_db)):
#     try:
#         visitor = db.execute(text("""
#             SELECT building_id FROM adoc_visitor WHERE adoc_visitor_id = :visitor_id
#         """), {"visitor_id": adoc_visitor_id}).mappings().first()

#         if not visitor:
#             raise HTTPException(status_code=404, detail="Visitor not found.")

#         building_id = visitor["building_id"]

#         device = db.execute(text("""
#             SELECT ip, user_name, password FROM camera_devices WHERE building_id = :building_id
#         """), {"building_id": building_id}).mappings().first()

#         if not device:
#             raise HTTPException(status_code=404, detail="Device not found for building.")

#         result = person_from_device(
#             employee_no=adoc_visitor_id,
#             DEVICE_IP=device["ip"],
#             USERNAME=device["user_name"],
#             # PASSWORD=device["password"] ,
#            PASSWORD= decrypt_password(device["password"])
#         )

#         if result["status"] == "success":
#             db.execute(text("""
#                 DELETE FROM adoc_visitor WHERE adoc_visitor_id = :visitor_id
#             """), {"visitor_id": adoc_visitor_id})
#             db.commit()

#         return result

#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))