from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import requests
import json
import cv2
from requests.auth import HTTPDigestAuth
from .models import AddPersonRequest
from DB.db import SessionLocal
import random
import shutil
import os
from fastapi import UploadFile ,APIRouter,HTTPException,File,Form,Depends,status
from utils.security import decrypt_password
import traceback
from fastapi import APIRouter, File, Form, UploadFile, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
import os, shutil, json, traceback
import requests
from requests.auth import HTTPDigestAuth
from utils.common_function import generate_employee_no

router = APIRouter()

UPLOAD_DIR = "uploaded_faces"  
FDID = "1"




# DEVICE_IP = "192.168.1.232"
# USERNAME = "admin"
# PASSWORD = "Psts@123"

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# def get_device_credentials(db: Session, building_id: int):
#     block_query = text("""
#         SELECT id FROM block
#         WHERE JSON_CONTAINS(building_ids, :b_id_json)
#     """)
#     block = db.execute(block_query, {"b_id_json": json.dumps(building_id)}).mappings().fetchone()

#     if not block:
#         return None

#     block_id = block["id"]

#     assign_query = text("SELECT device_id FROM assign_devices WHERE block_id = :block_id")
#     assign = db.execute(assign_query, {"block_id": block_id}).mappings().fetchone()

#     if not assign:
#         return None

#     device_id = assign["device_id"]

#     device_query = text("SELECT ip, user_name, password FROM camera_devices WHERE id = :device_id")
#     device = db.execute(device_query, {"device_id": device_id}).mappings().fetchone()

#     if not device:
#         return None
    
#     # decrypt_password = decrypt_password(device["password"])
    

#     return {
#         "device_id": device_id,
#         "DEVICE_IP": device["ip"],
#         "USERNAME": device["user_name"],
#         "PASSWORD": decrypt_password(device["password"])
#     }


def add_person_to_device(person: AddPersonRequest, DEVICE_IP, USERNAME, PASSWORD):
    url = f"https://{DEVICE_IP}/ISAPI/AccessControl/UserInfo/Record?format=json"

    if not person.employee_no:
        person.employee_no = generate_employee_no()

    payload = {
        "UserInfo": {
            "employeeNo": person.employee_no,
            "name": person.name,
            "userType": "normal",
            "Valid": {
                "enable": person.valid.enable,
                "beginTime": person.valid.beginTime.strftime("%Y-%m-%dT%H:%M:%S"),
                "endTime": person.valid.endTime.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeType": person.valid.timeType
            },
            "doorRight": person.door_right,
            "RightPlan": [{"doorNo": 1, "planTemplateNo": "1"}],
            "gender": person.gender,
            "localUIRight": True,
            "maxOpenDoorTime": 0,
            "userVerifyMode": "",
            "floorNumbers": [],
            "callNumbers": [],
            "password": ""
        }
    }
    print(f"\n Payload to Device ({DEVICE_IP}):\n{json.dumps(payload, indent=2)}")

    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(
            url,
            data=json.dumps(payload),
            headers=headers,
            auth=HTTPDigestAuth(USERNAME, PASSWORD),
            verify=False
        )

        if response.ok:
            return {
                "status": "success",
                "data": response.json(),
                "employee_no": person.employee_no
            }
        else:
            try:
                error_data = response.json()
            except Exception:
                error_data = response.text or "Unknown error"

            return {
                "status": "error",
                "error": error_data,
                "status_code": response.status_code
            }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }
    

    
def update_person_in_device(person, DEVICE_IP, USERNAME, PASSWORD):
    url = f"https://{DEVICE_IP}/ISAPI/AccessControl/UserInfo/Modify?format=json"

    begin_time_str = person.valid.beginTime.isoformat()
    end_time_str = person.valid.endTime.isoformat()

    payload = {
        "UserInfo": {
            "employeeNo": person.employee_no,
            "name": person.name,
            "userType": "normal",
            "Valid": {
                "enable": person.valid.enable,
                "beginTime": begin_time_str,
                "endTime": end_time_str,
                "timeType": person.valid.timeType
            },
            "doorRight": str(person.door_right or 0),
            "RightPlan": [{"doorNo": 1, "planTemplateNo": "1"}],
            "gender": person.gender or "male",
            "localUIRight": person.local_ui_right,
            "maxOpenDoorTime": person.max_open_door_time or 0,
            "userVerifyMode": person.user_verify_mode or "",
            "floorNumbers": person.floor_numbers or [],
            "callNumbers": person.call_numbers or [],
            "password": person.password or ""
        }
    }

    headers = {"Content-Type": "application/json"}
    try:
        response = requests.put(
            url,
            data=json.dumps(payload),
            headers=headers,
            auth=HTTPDigestAuth(USERNAME, PASSWORD),
            verify=False
        )
        print("DEBUG update_person_in_device payload:", payload)
        print("DEBUG update_person_in_device status:", response.status_code)

        if response.ok:
            try:
                return {"status": "success", "data": response.json()}
            except Exception:
                return {"status": "success", "data": response.text}
        else:
            return {"status": "error", "error": response.text, "status_code": response.status_code}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def update_person_in_db(db: Session, person, device_id: int):
    try:
        valid_data = {
            "enable": person.valid.enable,
            "beginTime": person.valid.beginTime.isoformat(),
            "endTime": person.valid.endTime.isoformat(),
            "timeType": person.valid.timeType
        }

        query = text("""
            UPDATE resident_device_assign
            SET name = :name,
                gender = :gender,
                valid = :valid,
                door_right = :door_right,
                right_plan = :right_plan,
                local_ui_right = :local_ui_right,
                max_open_door_time = :max_open_door_time,
                user_verify_mode = :user_verify_mode,
                floor_numbers = :floor_numbers,
                call_numbers = :call_numbers,
                password = :password,
                updated_at = NOW()
            WHERE user_id = :user_id AND device_id = :device_id
        """)

        db.execute(query, {
            "user_id": person.user_id,
            "device_id": device_id,
            "name": person.name,
            "gender": person.gender,
            "valid": json.dumps(valid_data),
            "door_right": person.door_right or 0,
            "right_plan": json.dumps([{"doorNo": 1, "planTemplateNo": "1"}]),
            "local_ui_right": person.local_ui_right,
            "max_open_door_time": person.max_open_door_time or 0,
            "user_verify_mode": person.user_verify_mode or "",
            "floor_numbers": json.dumps(person.floor_numbers or []),
            "call_numbers": json.dumps(person.call_numbers or []),
            "password": person.password or "",
        })
        db.commit()
        return {"status": "success"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}

    

def delete_person_from_device(employee_no: str, DEVICE_IP: str, USERNAME: str, PASSWORD: str):
 
    url = f"https://{DEVICE_IP}/ISAPI/AccessControl/UserInfo/Delete?format=json"

    payload = {
        "UserInfoDelCond": {
            "EmployeeNoList": [{"employeeNo": employee_no}]
        }
    }

    headers = {"Content-Type": "application/json"}

    print(f"\nPayload for Delete ({DEVICE_IP}):\n{json.dumps(payload, indent=2)}")

    try:
        response = requests.put(
            url,
            data=json.dumps(payload),
            headers=headers,
            auth=HTTPDigestAuth(USERNAME, PASSWORD),
            verify=False
        )

        if response.ok:
            return {
                "status": "success",
                "data": response.json(),
                "employee_no": employee_no
            }
        else:
            try:
                error_data = response.json()
            except Exception:
                error_data = response.text or "Unknown error"

            return {
                "status": "error",
                "error": error_data,
                "status_code": response.status_code
            }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

def upload_qr_card(device_ip, username, password,
                   visitor_id, card_no, valid_from, valid_to):
    url = f"http://{device_ip}/ISAPI/AccessControl/CardInfo/Record?format=json"
    payload = {
        "CardInfo": {
            "employeeNo": visitor_id,
            "cardNo": card_no,
            "cardType": "normalCard",
            "status": "active",
            "doorRight": "10",
            "valid": {
                "enable": True,
                "beginTime": valid_from,
                "endTime": valid_to
            }
        }
    }
    print(f"\n Payload to Device {payload}")

    res = requests.post(url, auth=requests.auth.HTTPDigestAuth(username, password),
                        json=payload, verify=False)
    return res.status_code == 200, res.text



def generate_next_employee_no(db: Session):
    latest = db.execute(
        text("SELECT employee_no FROM resident_device_assign WHERE employee_no LIKE 'EMP%' ORDER BY id DESC LIMIT 1")
    ).fetchone()

    if latest and latest[0]:
        try:
            number = int(latest[0].replace("EMP", ""))
            next_number = number + 1
        except ValueError:
            next_number = 1
    else:
        next_number = 1

    return f"EMP{str(next_number).zfill(2)}"

def store_person_in_db(db: Session, person: AddPersonRequest, device_id: int):
    try:
        employee_no = person.employee_no or generate_next_employee_no(db)

        query = text("""
            INSERT INTO resident_device_assign (
                user_id, employee_no, name, gender,
                valid,
                door_right, right_plan, local_ui_right, max_open_door_time,
                user_verify_mode, floor_numbers, call_numbers, password,
                device_id,
                created_at
            ) VALUES (
                :user_id, :employee_no, :name, :gender,
                :valid,
                :door_right, :right_plan, :local_ui_right, :max_open_door_time,
                :user_verify_mode, :floor_numbers, :call_numbers, :password,
                :device_id,
                NOW()
            )
        """)

        db.execute(query, {
            "user_id": person.user_id or 1,
            "employee_no": employee_no,
            "name": person.name,
            "device_id":device_id,
            "gender": person.gender,
            "valid": json.dumps({
                "enable": person.valid.enable,
                "beginTime": person.valid.beginTime.isoformat(),
                "endTime": person.valid.endTime.isoformat(),
                "timeType": person.valid.timeType
            }),
            "door_right": person.door_right,
            "right_plan": json.dumps([rp.dict() for rp in person.right_plan]),
            "local_ui_right": person.local_ui_right,
            "max_open_door_time": person.max_open_door_time,
            "user_verify_mode": person.user_verify_mode,
            "floor_numbers": json.dumps(person.floor_numbers),
            "call_numbers": json.dumps(person.call_numbers),
            "password": person.password,
        })
        db.commit()
        return {"status": "success", "employee_no": employee_no}

    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    

FDID = "1"
UPLOAD_DIR = "uploaded_faces"
os.makedirs(UPLOAD_DIR, exist_ok=True)
 


def validate_face(image_path: str) -> bool:
    """Return True if at least one face is detected, else False."""
    try:
        img = cv2.imread(image_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        face_cascade = cv2.CascadeClassifier(cascade_path)

        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
        return len(faces) > 0
    except Exception as e:
        print(f"[Face Validation Error] {e}")
        return False


@router.post("/face_upload")
async def upload_face_by_employee_no(
    employee_no: str = Form(...),
    building_id: str = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        building_check = db.execute(text("""
            SELECT COUNT(*) as count 
            FROM camera_devices 
            WHERE building_id = :building_id
        """), {"building_id": building_id}).mappings().first()

        if building_check["count"] == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No devices assigned to building_id: {building_id}"
            )

        device_query = text("""
            SELECT id, ip, user_name, password
            FROM camera_devices
            WHERE building_id = :building_id OR common_building = 'common'
        """)
        devices = db.execute(device_query, {"building_id": building_id}).mappings().fetchall()

        if not devices:
            raise HTTPException(status_code=404, detail="No devices found")

        os.makedirs(UPLOAD_DIR, exist_ok=True)
        saved_path = os.path.join(UPLOAD_DIR, f"{employee_no}.jpg")
        with open(saved_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

        if not validate_face(saved_path):
            os.remove(saved_path) 
            raise HTTPException(
                status_code=400,
                detail={
                    "message":"Oops! We couldn’t detect a face in your upload."
                }
            )

        payload = {
            "faceLibType": "blackFD",
            "FDID": FDID,
            "FPID": employee_no
        }

        success_devices = []
        failed_devices = []

        for device in devices:
            device_id = device["id"]
            DEVICE_IP = device["ip"]
            USERNAME = device["user_name"]
            PASSWORD = decrypt_password(device["password"])

            url = f"http://{DEVICE_IP}/ISAPI/Intelligent/FDLib/FaceDataRecord?format=json"

            try:
                with open(saved_path, 'rb') as img_file:
                    files = {
                        "FaceDataRecord": ("FaceDataRecord", json.dumps(payload), "application/json"),
                        "img": ("face.jpg", img_file, "image/jpeg")
                    }

                    response = requests.post(
                        url,
                        auth=HTTPDigestAuth(USERNAME, PASSWORD),
                        files=files,
                        timeout=10,
                        verify=False
                    )

                print(f"\n[Upload] Device {DEVICE_IP}")
                print(f"Status: {response.status_code}")
                print(f"Response: {response.text}")

                if response.status_code == 200:
                    upsert_query = text("""
                        INSERT INTO resident_device_assign 
                            (employee_no, device_id, image_upload_path, building_id)
                        VALUES (:employee_no, :device_id, :image_path, :building_id)
                        ON DUPLICATE KEY UPDATE 
                            image_upload_path = VALUES(image_upload_path),
                            building_id = VALUES(building_id)
                    """)
                    db.execute(upsert_query, {
                        "employee_no": employee_no,
                        "device_id": device_id,
                        "image_path": saved_path.replace("\\", "/"),
                        "building_id": building_id
                    })
                    success_devices.append(DEVICE_IP)
                else:
                    try:
                        error_json = response.json()
                    except Exception:
                        error_json = {"raw_response": response.text}

                    failed_devices.append({
                        "device_ip": DEVICE_IP,
                        "status_code": response.status_code,
                        "hikvision_error": error_json
                    })

            except Exception as e:
                failed_devices.append({
                    "device_ip": DEVICE_IP,
                    "error": str(e)
                })

        db.commit()

        message = f"Upload attempted on {len(devices)} devices."
        for fd in failed_devices:
            hik_err = fd.get("hikvision_error", {})
            if isinstance(hik_err, dict):
                sub_code = hik_err.get("subStatusCode", "")
                if sub_code == "deviceUserAlreadyExistFace":
                    message = "Face already exists on one or more devices."
                    break
                elif sub_code in ["SubpicAnalysisModelingError", "invalidPic", "facePicError"]:
                    message = "Oops! We couldn’t detect a face in your upload."
                    break

        response_body = {
            "status": "completed",
            "message": message,
            "success_devices": success_devices,
            "failed_devices": failed_devices,
            "request_payload": payload,
            "image_upload_path": saved_path.replace("\\", "/")
        }

        if not success_devices:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=response_body
            )

        return response_body

    except HTTPException as he:
        raise he
    except Exception as e:
        print("Traceback:\n", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")