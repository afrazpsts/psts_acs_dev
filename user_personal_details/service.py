from fastapi import APIRouter, Depends, HTTPException, Request, Query,BackgroundTasks,FastAPI,Form
from sqlalchemy.orm import Session
from sqlalchemy import text
from DB.db import SessionLocal
from utils.security import verify_token
from datetime import datetime,timedelta, date, datetime
from sqlalchemy.exc import IntegrityError
import traceback
from requests.auth import HTTPDigestAuth
from typing import Optional
from passlib.context import CryptContext
from.models import LoginRequest,OTPVerifyRequest,ResendOTPRequest,SetPasswordRequest,EmailRequest,EmailVerifyRequest,LicensePlateRequest,UpdatePlateRequest,LogoutRequest
from resident_device_assign.service import add_person_to_device, store_person_in_db,upload_qr_card,delete_person_from_device,update_person_in_device,update_person_in_db
from resident_device_assign.models import AddPersonRequest,ValidTime,UpdatePersonRequest
from passlib.hash import bcrypt
import random
from zoneinfo import ZoneInfo
from utils.mailjet_service import send_otp_email,send_onboarding_email
from utils.security import hash_password,create_access_token,create_refresh_token ,decrypt_password
from utils.common_function import generate_card_number,generate_otp
from concurrent.futures import ThreadPoolExecutor
import threading
import json
from anpr_camera_assign.service import upload_license_plate_info,insert_license_plate
from activity_logs.service import log_activity
router = APIRouter()

IST = ZoneInfo("Asia/Kolkata")
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



executor = ThreadPoolExecutor(max_workers=20)

def process_device_parallel(device, user_data, access, card_no, user_id, user_email, user_type):
    """Process a single device and store in resident_device_assign table"""
    try:
        access_begin = (
            access["access_start"].replace(" ", "T")
            if " " in access["access_start"]
            else access["access_start"] + "T00:00:00"
        )
        access_end = (
            access["access_end"].replace(" ", "T")
            if " " in access["access_end"]
            else access["access_end"] + "T00:00:00"
        )

        person = AddPersonRequest(
            user_id=user_id,
            name=user_data["name"],
            gender=user_data["gender"],
            valid={
                "enable": True,
                "beginTime": access_begin,
                "endTime": access_end,
                "timeType": "local"
            }
        )

        device_response = add_person_to_device(
            person,
            device["DEVICE_IP"],
            device["USERNAME"],
            decrypt_password(device["PASSWORD"])
        )

        if device_response.get("status") == "success":
            success, response_text = upload_qr_card(
                device_ip=device["DEVICE_IP"],
                username=device["USERNAME"],
                password=decrypt_password(device["PASSWORD"]),
                visitor_id=device_response.get("employee_no"),
                card_no=card_no,
                valid_from=access_begin,
                valid_to=access_end
            )
            
            print(f" {user_type} user {user_email} added to device {device['DEVICE_IP']}")
            
            return {
                "success": True,
                "user_id": user_id,
                "employee_no": device_response.get("employee_no"),
                "device_id": device["device_id"],
                "device_ip": device["DEVICE_IP"],
                "name": user_data["name"],
                "gender": user_data["gender"],
                "building_id": access["building_id"],
                "valid": {
                    "enable": True,
                    "beginTime": access_begin,
                    "endTime": access_end,
                    "timeType": "local"
                },
                "door_right": "1",
                "right_plan": [{"doorNo": 1, "planTemplateNo": "1"}],
                "local_ui_right": True,
                "max_open_door_time": 0,
                "user_verify_mode": "",
                "floor_numbers": [],
                "call_numbers": [],
                "password": ""
            }
        else:
            print(f" Failed to add {user_type} user {user_email} to device {device['DEVICE_IP']}")
            return None
            
    except Exception as e:
        print(f" Error: {user_email} on {device.get('DEVICE_IP')}: {str(e)}")
        return None


def send_emails_parallel(emails_data):
    """Send multiple emails in parallel"""
    from concurrent.futures import as_completed
    
    futures = []
    for email_data in emails_data:
        future = executor.submit(send_onboarding_email, **email_data)
        futures.append(future)
    
    for future in as_completed(futures):
        result = future.result()
        if result:
            print(f" Email sent successfully")
        else:
            print(f" Email failed")


# def insert_license_plate(db: Session, plate_info: dict):
#     """Insert license plate into database"""
#     print(f"[LOG] Inserting license plate: {plate_info}")
    
#     if plate_info["listType"] == "blockList":
#         query = text("""
#             INSERT INTO license_plate_access (
#                 LicensePlate, vehicle_type, iu_number, building_id, resident_id, listType
#             ) VALUES (
#                 :LicensePlate, :vehicle_type, :iu_number, :building_id, :resident_id, :listType
#             )
#         """)
#         params = {
#             "building_id": plate_info["building_id"],
#             "resident_id": plate_info["resident_id"],
#             "LicensePlate": plate_info["LicensePlate"],
#             "vehicle_type": plate_info["vehicle_type"],
#             "iu_number": plate_info["iu_number"],
#             "listType": plate_info["listType"]
#         }
#     else:
#         query = text("""
#             INSERT INTO license_plate_access (
#                 LicensePlate, vehicle_type, iu_number, building_id, resident_id, listType, 
#                 createTime, effectiveTime
#             ) VALUES (
#                 :LicensePlate, :vehicle_type, :iu_number, :building_id, :resident_id, :listType, 
#                 :createTime, :effectiveTime
#             )
#         """)
#         params = {
#             "building_id": plate_info["building_id"],
#             "resident_id": plate_info["resident_id"],
#             "LicensePlate": plate_info["LicensePlate"],
#             "vehicle_type": plate_info["vehicle_type"],
#             "iu_number": plate_info["iu_number"],
#             "listType": plate_info["listType"],
#             "createTime": plate_info["createTime"],
#             "effectiveTime": plate_info["effectiveTime"]
#         }
    
#     try:
#         db.execute(query, params)
#         db.commit()
#         print(f" License plate {plate_info['LicensePlate']} inserted successfully")
#         return {"message": "License plate inserted successfully"}
#     except IntegrityError as e:
#         db.rollback()
#         error_message = str(e.orig).lower()
#         if "uq_card_no" in error_message or "cardno" in error_message:
#             raise HTTPException(
#                 status_code=400,
#                 detail=f"IU Number '{plate_info['cardNo']}' already exists."
#             )
#         elif "uq_license_plate" in error_message or "licenseplate" in error_message:
#             raise HTTPException(
#                 status_code=400,
#                 detail=f"License plate '{plate_info['LicensePlate']}' already exists."
#             )
#         else:
#             raise HTTPException(status_code=400, detail=f"Duplicate entry: {error_message}")


# def process_license_plate_for_devices(vehicles, building_id, resident_id, access, background_tasks, db):
#     """Process license plates for a resident and upload to ANPR devices"""
#     if not vehicles:
#         return []
    
#     print(f"\n🚗 Processing {len(vehicles)} vehicle(s) for resident {resident_id}")
    
#     building_devices = db.execute(text("""
#         SELECT id, ip, user_name, password
#         FROM camera_devices
#         WHERE building_id = :building_id AND type = 2
#     """), {"building_id": building_id}).fetchall()
    
#     common_devices = db.execute(text("""
#         SELECT id, ip, user_name, password
#         FROM camera_devices
#         WHERE common_building = 'common' AND type = 2
#     """)).fetchall()
    
#     all_devices = []
#     device_ids = set()
#     for device in building_devices + common_devices:
#         if device[0] not in device_ids:
#             device_ids.add(device[0])
#             all_devices.append({
#                 "device_id": device[0],
#                 "DEVICE_IP": device[1],
#                 "USERNAME": device[2],
#                 "PASSWORD": device[3]
#             })
    
#     if not all_devices:
#         print("⚠️ No ANPR devices found, skipping license plate upload")
#         return []
    
#     print(f"📱 Found {len(all_devices)} ANPR device(s)")
    
#     processed_vehicles = []
#     for vehicle in vehicles:
#         try:
#             plate_info = {
#                 "LicensePlate": vehicle["license_plate"],
#                 "cardNo": vehicle.get("cardno", generate_card_number()),
#                 "building_id": building_id,
#                 "resident_id": resident_id,
#                 "vehicle_type": vehicle.get("vehicle_type", "Car"),
#                 "listType": "whiteList",  
#                 "createTime": access["access_start"] if access else None,
#                 "effectiveTime": access["access_end"] if access else None
#             }
            
#             insert_license_plate(db, plate_info)
            
#             # Upload to all ANPR devices in background
#             # def upload_plate_to_devices():
#             #     from DB.db import SessionLocal
#             #     import requests
#             #     from requests.auth import HTTPDigestAuth
                
#             #     db_session = SessionLocal()
#             #     uploaded = []
#             #     failed = []
                
#             #     for device in all_devices:
#             #         try:
#             #             # Prepare device payload
#             #             device_plate_info = {
#             #                 "LicensePlate": plate_info["LicensePlate"],
#             #                 "cardID": "",
#             #                 "cardNo": plate_info["cardNo"],
#             #                 "certificateNumber": "",
#             #                 "certificateType": "ID",
#             #                 "building_id": plate_info["building_id"],
#             #                 "resident_id": plate_info["resident_id"],
#             #                 "vehicle_type": plate_info["vehicle_type"],
#             #                 "listType": plate_info["listType"],
#             #                 "name": "",
#             #                 "operation": "new",
#             #                 "operationType": "add",
#             #                 "plateColor": "blue",
#             #                 "plateDescription": "",
#             #                 "plateType": "92TypeCivil",
#             #                 "virtualParkingNum": "",
#             #                 "createTime": plate_info["createTime"],
#             #                 "effectiveTime": plate_info["effectiveTime"]
#             #             }
                        
#             #             # Upload to device
#             #             url = f"http://{device['DEVICE_IP']}/ISAPI/Intelligent/FD/LPR/WhiteList/Record?format=json"
#             #             response = requests.post(
#             #                 url,
#             #                 json=device_plate_info,
#             #                 auth=HTTPDigestAuth(device["USERNAME"], decrypt_password(device["PASSWORD"])),
#             #                 timeout=10,
#             #                 verify=False
#             #             )
                        
#             #             if response.status_code in [200, 201]:
#             #                 uploaded.append(device['DEVICE_IP'])
#             #                 print(f" Plate {plate_info['LicensePlate']} uploaded to {device['DEVICE_IP']}")
#             #             else:
#             #                 failed.append(device['DEVICE_IP'])
#             #                 print(f" Failed to upload plate to {device['DEVICE_IP']}: {response.status_code}")
                    
#             #         except Exception as e:
#             #             failed.append(device['DEVICE_IP'])
#             #             print(f"⚠️ Error uploading plate to {device['DEVICE_IP']}: {str(e)}")
                
#             #     # Update device activities in database
#             #     if uploaded or failed:
#             #         db_session.execute(
#             #             text("UPDATE license_plate_access SET anpr_device_activities = :activities WHERE LicensePlate = :plate AND resident_id = :rid"),
#             #             {
#             #                 "activities": json.dumps({"uploaded": uploaded, "failed": failed}),
#             #                 "plate": plate_info["LicensePlate"],
#             #                 "rid": resident_id
#             #             }
#             #         )
#             #         db_session.commit()
                
#             #     db_session.close()
#             #     return {"uploaded": uploaded, "failed": failed}
            
#             # # Add to background tasks
#             # background_tasks.add_task(upload_plate_to_devices)
            
#             processed_vehicles.append({
#                 "license_plate": vehicle["license_plate"],
#                 "vehicle_type": vehicle.get("vehicle_type"),
#                 "card_no": plate_info["cardNo"],
#                 "status": "processing"
#             })
            
#         except HTTPException as e:
#             print(f" Failed to add vehicle {vehicle.get('license_plate')}: {str(e.detail)}")
#             processed_vehicles.append({
#                 "license_plate": vehicle.get("license_plate"),
#                 "error": str(e.detail)
#             })
#         except Exception as e:
#             print(f" Error processing vehicle: {str(e)}")
#             processed_vehicles.append({
#                 "license_plate": vehicle.get("license_plate"),
#                 "error": str(e)
#             })
    
#     return processed_vehicles


@router.post("/create_resident")
async def create_user_personal_details(
    request: Request, 
    background_tasks: BackgroundTasks, 
    creator_email: Optional[str] = Form(None, description="Email of the person creating the resident record"),
    db: Session = Depends(get_db)
):
    try:
        ip_address = request.client.host if request and request.client else "Unknown"
        
        # Get creator information similar to marketing endpoint
        creator_id = None
        creator_name = "Unknown"
        creator_company_id = None
        
        print(f"Creator email received: {creator_email}")
        
        if creator_email:
            creator_info = db.execute(
                text("SELECT id, name, company_id FROM users WHERE LOWER(email) = LOWER(:email)"),  
                {"email": creator_email}
            ).fetchone()
            
            if creator_info:
                creator_id = creator_info[0]
                creator_name = creator_info[1]
                creator_company_id = creator_info[2]
                print(f"Found user: ID={creator_id}, Name={creator_name}")
            else:
                if creator_email.lower() == "bmoadmin@yopmail.com":
                    creator_id = 7
                    creator_name = "BMO Admin"
                    creator_company_id = None
                    print("Using BMO Admin special case")
                else:
                    creator_info = db.execute(
                        text("SELECT id, name, company_id FROM users WHERE email = :email"),  
                        {"email": creator_email}
                    ).fetchone()
                    
                    if creator_info:
                        creator_id = creator_info[0]
                        creator_name = creator_info[1]
                        creator_company_id = creator_info[2]
                        print(f"Found user with exact match: ID={creator_id}")
                    else:
                        print(f"Email {creator_email} not found in users table")
                        creator_id = 1  
                        creator_name = "System Admin"
                        creator_company_id = None
        
        print(f"Final creator info - ID: {creator_id}, Name: {creator_name}, Email: {creator_email}")
        
        data = await request.json()
        now = datetime.now()
        
        sub_users_list = data.get("sub_users", [])
        vehicles_list = data.get("vehicles", [])
        
        all_emails = [data["email"]]
        for sub in sub_users_list:
            if sub.get("email"):
                all_emails.append(sub["email"])
        
        placeholders = ','.join([f"'{email}'" for email in all_emails])
        email_check_query = text(f"""
            SELECT email FROM user_personal_details 
            WHERE email IN ({placeholders})
        """)
        existing_emails = db.execute(email_check_query).fetchall()
        
        if existing_emails:
            existing_email_list = [row[0] for row in existing_emails]
            raise HTTPException(
                status_code=400, 
                detail=f"These emails already exist: {', '.join(existing_email_list)}"
            )
        
        otp = generate_otp()
        otp_expiry = now + timedelta(minutes=15)
        card_no = generate_card_number()

        access = data.get("access_details")
        devices = []  
        anpr_devices = []

        if access:
            devices = db.execute(text("""
                SELECT 
                    cd.id AS device_id,
                    cd.ip AS DEVICE_IP,
                    cd.user_name AS USERNAME,
                    cd.password AS PASSWORD,
                    cd.name AS device_name
                FROM assign_devices ad
                JOIN camera_devices cd ON ad.device_id = cd.id
                WHERE ad.building_id = :building_id AND cd.type != 2
            """), {"building_id": access["building_id"]}).mappings().fetchall()
            
            anpr_devices = db.execute(text("""
                SELECT 
                    cd.id AS device_id,
                    cd.ip AS DEVICE_IP,
                    cd.user_name AS USERNAME,
                    cd.password AS PASSWORD,
                    cd.name AS device_name
                FROM assign_devices ad
                JOIN camera_devices cd ON ad.device_id = cd.id
                WHERE ad.building_id = :building_id AND cd.type = 2
            """), {"building_id": access["building_id"]}).mappings().fetchall()
            
            common_anpr_devices = db.execute(text("""
                SELECT 
                    id AS device_id,
                    ip AS DEVICE_IP,
                    user_name AS USERNAME,
                    password AS PASSWORD,
                    name AS device_name
                FROM camera_devices
                WHERE common_building = 'common' AND type = 2
            """)).mappings().fetchall()
            
            anpr_devices.extend(common_anpr_devices)

            if not devices:
                raise HTTPException(status_code=404, detail="No access control devices assigned to this building")
            
            print(f" Found {len(devices)} access control device(s) for building {access['building_id']}")
            print(f" Found {len(anpr_devices)} ANPR device(s) for license plates")

        personal_query = text("""
            INSERT INTO user_personal_details
            (first_name, middle_name, last_name, email, dob, gender, nationality,
             identity_number, phone, country_code, address, country, city, zipcode,
             otp, otp_expiry, created_at, updated_at, card_no)
            VALUES
            (:first_name, :middle_name, :last_name, :email, :dob, :gender, :nationality,
             :identity_number, :phone, :country_code, :address, :country, :city, :zipcode,
             :otp, :otp_expiry, :created_at, :updated_at, :card_no)
        """)
        result = db.execute(personal_query, {
            "first_name": data["first_name"],
            "middle_name": data.get("middle_name"),
            "last_name": data["last_name"],
            "email": data["email"],
            "dob": data.get("dob"),
            "gender": data.get("gender"),
            "nationality": data.get("nationality"),
            "identity_number": data.get("identity_number"),
            "phone": data.get("phone"),
            "country_code": data.get("country_code"),
            "address": data.get("address"),
            "country": data.get("country"),
            "city": data.get("city"),
            "zipcode": data.get("zipcode"),
            "otp": otp,
            "otp_expiry": otp_expiry,
            "created_at": now,
            "updated_at": now,
            "card_no": card_no
        })
        main_user_id = result.lastrowid

        emergency = data.get("emergency_details")
        if emergency:
            emergency_query = text("""
                INSERT INTO user_emergency
                (user_id, first_name, last_name, email, phone, country_code,
                 gender, nationality, relationship, created_at, updated_at)
                VALUES
                (:user_id, :first_name, :last_name, :email, :phone, :country_code,
                 :gender, :nationality, :relationship, :created_at, :updated_at)
            """)
            db.execute(emergency_query, {
                "user_id": main_user_id,
                "first_name": emergency.get("first_name", ""),
                "last_name": emergency.get("last_name"),
                "email": emergency.get("email"),
                "phone": emergency.get("phone"),
                "country_code": emergency.get("country_code"),
                "gender": emergency.get("gender"),
                "nationality": emergency.get("nationality"),
                "relationship": emergency.get("relationship"),
                "created_at": now,
                "updated_at": now
            })

        if access:
            access_query = text("""
                INSERT INTO user_access_details
                (user_id, residency_type_id, building_id, level_id, unit_id,
                 join_date, access_start, access_end, created_at, updated_at)
                VALUES
                (:user_id, :residency_type_id, :building_id, :level_id, :unit_id,
                 :join_date, :access_start, :access_end, :created_at, :updated_at)
            """)
            db.execute(access_query, {
                "user_id": main_user_id,
                "residency_type_id": access["residency_type_id"],
                "building_id": access["building_id"],
                "level_id": access["level_id"],
                "unit_id": access["unit_id"],
                "join_date": access["join_date"],
                "access_start": access["access_start"],
                "access_end": access["access_end"],
                "created_at": now,
                "updated_at": now
            })

        sub_user_ids = []
        created_sub_users = []
        all_users_for_devices = []
        
        all_users_for_devices.append({
            "user_id": main_user_id,
            "name": data["first_name"],
            "gender": data.get("gender", "male").lower(),
            "email": data["email"],
            "card_no": card_no,
            "type": "main"
        })
        
        for sub in sub_users_list:
            if not sub.get("email"):
                raise HTTPException(
                    status_code=400, 
                    detail=f"Email is required for sub-user: {sub.get('first_name')}"
                )
            
            sub_otp = generate_otp()
            sub_card_no = generate_card_number()
            
            sub_personal_query = text("""
                INSERT INTO user_personal_details
                (first_name, middle_name, last_name, email, dob, gender, nationality,
                 identity_number, phone, country_code, address, country, city, zipcode,
                 otp, otp_expiry, created_at, updated_at, card_no)
                VALUES
                (:first_name, :middle_name, :last_name, :email, :dob, :gender, :nationality,
                 :identity_number, :phone, :country_code, :address, :country, :city, :zipcode,
                 :otp, :otp_expiry, :created_at, :updated_at, :card_no)
            """)
            
            sub_result = db.execute(sub_personal_query, {
                "first_name": sub.get("first_name"),
                "middle_name": sub.get("middle_name"),
                "last_name": sub.get("last_name"),
                "email": sub["email"],
                "dob": sub.get("dob") or data.get("dob"),
                "gender": sub.get("gender") or data.get("gender"),
                "nationality": sub.get("nationality") or data.get("nationality"),
                "identity_number": sub.get("identity_number"),
                "phone": sub.get("phone") or data.get("phone"),
                "country_code": sub.get("country_code") or data.get("country_code"),
                "address": sub.get("address") or data.get("address"),
                "country": sub.get("country") or data.get("country"),
                "city": sub.get("city") or data.get("city"),
                "zipcode": sub.get("zipcode") or data.get("zipcode"),
                "otp": sub_otp,
                "otp_expiry": otp_expiry,
                "created_at": now,
                "updated_at": now,
                "card_no": sub_card_no
            })
            
            sub_user_id = sub_result.lastrowid
            sub_user_ids.append(sub_user_id)
            
            all_users_for_devices.append({
                "user_id": sub_user_id,
                "name": sub.get("first_name"),
                "gender": sub.get("gender") or data.get("gender", "male").lower(),
                "email": sub["email"],
                "card_no": sub_card_no,
                "type": "sub"
            })
            
            if access:
                sub_access_query = text("""
                    INSERT INTO user_access_details
                    (user_id, residency_type_id, building_id, level_id, unit_id,
                     join_date, access_start, access_end, created_at, updated_at)
                    VALUES
                    (:user_id, :residency_type_id, :building_id, :level_id, :unit_id,
                     :join_date, :access_start, :access_end, :created_at, :updated_at)
                """)
                
                residency_type_id = sub.get("residency_type_id") or access["residency_type_id"]
                
                db.execute(sub_access_query, {
                    "user_id": sub_user_id,
                    "residency_type_id": residency_type_id,
                    "building_id": access["building_id"],
                    "level_id": access["level_id"],
                    "unit_id": access["unit_id"],
                    "join_date": access["join_date"],
                    "access_start": access["access_start"],
                    "access_end": access["access_end"],
                    "created_at": now,
                    "updated_at": now
                })
            
            link_query = text("""
                INSERT INTO resident_family_members
                (main_user_id, sub_user_id, relationship, created_at, updated_at)
                VALUES
                (:main_user_id, :sub_user_id, :relationship, :created_at, :updated_at)
            """)
            db.execute(link_query, {
                "main_user_id": main_user_id,
                "sub_user_id": sub_user_id,
                "relationship": sub.get("relationship"),
                "created_at": now,
                "updated_at": now
            })
            
            created_sub_users.append({
                "id": sub_user_id,
                "first_name": sub.get("first_name"),
                "last_name": sub.get("last_name"),
                "email": sub["email"],
                "relationship": sub.get("relationship"),
                "residency_type_id": sub.get("residency_type_id") or (access["residency_type_id"] if access else None),
                "card_no": sub_card_no,
                "otp": sub_otp
            })

        created_plates = []
        
        for vehicle in vehicles_list:
            if not vehicle.get("license_plate"):
                continue
            
            existing_plate = db.execute(
                text("""
                    SELECT id FROM license_plate_access
                    WHERE LicensePlate = :LicensePlate
                    AND building_id = :building_id
                    LIMIT 1
                """),
                {
                    "LicensePlate": vehicle["license_plate"],
                    "building_id": access["building_id"] if access else None
                }
            ).fetchone()
            
            if existing_plate:
                print(f" License plate {vehicle['license_plate']} already exists, skipping...")
                continue
            
            list_type = vehicle.get("listType", "allowList")
            
            create_time_value = None
            effective_time_value = None
            
            if list_type != "blockList" and access:
                if "T" in access["access_start"]:
                    create_time_value = access["access_start"]
                else:
                    create_time_value = f"{access['access_start']}T00:00:00"
                    
                if "T" in access["access_end"]:
                    effective_time_value = access["access_end"]
                else:
                    effective_time_value = f"{access['access_end']}T23:59:59"
                
                print(f"  Formatted times for DB - createTime: {create_time_value}, effectiveTime: {effective_time_value}")

                iu_number = vehicle.get("iu_number")
            
            plate_info = {
                "LicensePlate": vehicle["license_plate"],
                "iu_number": iu_number,
                "building_id": access["building_id"] if access else None,
                "resident_id": main_user_id,
                "vehicle_type": vehicle.get("vehicle_type", "car"),
                "listType": list_type,
                "createTime": create_time_value,
                "effectiveTime": effective_time_value,
                "source": "resident"
            }
            
            try:
                if plate_info["listType"] == "blockList":
                    insert_plate_query = text("""
                        INSERT INTO license_plate_access (
                            LicensePlate, vehicle_type, iu_number, building_id, resident_id, listType,source
                        ) VALUES (
                            :LicensePlate, :vehicle_type, :iu_number, :building_id, :resident_id, :listType,:source
                        )
                    """)
                    params = {
                        "building_id": plate_info["building_id"],
                        "resident_id": plate_info["resident_id"],
                        "LicensePlate": plate_info["LicensePlate"],
                        "vehicle_type": plate_info["vehicle_type"],
                        "iu_number": plate_info["iu_number"],
                        "listType": plate_info["listType"],
                        "source": plate_info["source"]

                    }
                else:
                    insert_plate_query = text("""
                        INSERT INTO license_plate_access (
                            LicensePlate, vehicle_type, iu_number, building_id, resident_id, listType, 
                            createTime, effectiveTime,source
                        ) VALUES (
                            :LicensePlate, :vehicle_type, :iu_number, :building_id, :resident_id, :listType,
                            :createTime, :effectiveTime,:source
                        )
                    """)
                    params = {
                        "building_id": plate_info["building_id"],
                        "resident_id": plate_info["resident_id"],
                        "LicensePlate": plate_info["LicensePlate"],
                        "vehicle_type": plate_info["vehicle_type"],
                        "iu_number": plate_info["iu_number"],
                        "listType": plate_info["listType"],
                        "createTime": plate_info["createTime"],
                        "effectiveTime": plate_info["effectiveTime"],
                        "source": plate_info["source"]
                    }
                
                db.execute(insert_plate_query, params)
                
                created_plates.append({
                    "license_plate": vehicle["license_plate"],
                    "vehicle_type": vehicle.get("vehicle_type", "car"),
                    "iu_number": iu_number,
                    "listType": list_type,
                    "createTime": create_time_value,
                    "effectiveTime": effective_time_value
                })
                print(f" License plate {vehicle['license_plate']} inserted into database with listType: {list_type}, createTime: {create_time_value}, effectiveTime: {effective_time_value}")
                
            except Exception as e:
                print(f" Error inserting license plate {vehicle['license_plate']}: {str(e)}")

        db.commit()

        # Log successful resident creation
        log_user_id = creator_id if creator_id is not None else 1
        
        log_activity(
            db=db,
            user_id=log_user_id,
            action="Create",
            module_name="Resident",
            record_id=main_user_id,
            description=f"Resident record created successfully – {data['first_name']} {data.get('last_name', '')}",
            new_data={
                "payload": {
                    "main_user": {
                        "first_name": data["first_name"],
                        "last_name": data["last_name"],
                        "email": data["email"],
                        "phone": data.get("phone"),
                        "card_no": card_no
                    },
                    "sub_users_count": len(sub_user_ids),
                    "vehicles_count": len(created_plates),
                    "has_access": access is not None,
                    "building_id": access["building_id"] if access else None,
                    "unit_id": access["unit_id"] if access else None
                },
                "result": {
                    "main_user_id": main_user_id,
                    "sub_users": created_sub_users,
                    "license_plates": created_plates
                },
                "creator_info": {
                    "creator_id": creator_id,
                    "creator_email": creator_email,
                    "creator_name": creator_name,
                    "creator_company_id": creator_company_id
                }
            },
            ip_address=ip_address
        )
        
        if access:
            building_name = db.execute(text("""
                SELECT building_name FROM property_building WHERE id = :id
            """), {"id": access["building_id"]}).scalar() or "Your Building"
            
            emails_data = []
            emails_data.append({
                "email": data["email"],
                "first_name": data["first_name"],
                "building_name": building_name,
                "on_board_date": access["access_start"],
                "off_board_date": access["access_end"]
            })
            
            for sub in created_sub_users:
                emails_data.append({
                    "email": sub["email"],
                    "first_name": sub["first_name"],
                    "building_name": building_name,
                    "on_board_date": access["access_start"],
                    "off_board_date": access["access_end"]
                })
            
            background_tasks.add_task(send_emails_parallel, emails_data)
        
            if devices:
                def process_all_devices_and_users():
                    from DB.db import SessionLocal
                    import json
                    from concurrent.futures import ThreadPoolExecutor
                    
                    print(f"\n Starting access control device sync for {len(all_users_for_devices)} users on {len(devices)} devices...")
                    
                    all_tasks = []
                    for user in all_users_for_devices:
                        for device in devices:
                            all_tasks.append({
                                "device": device,
                                "user": user,
                                "access": access,
                                "card_no": user["card_no"],
                                "user_id": user["user_id"],
                                "user_email": user["email"],
                                "user_type": user["type"]
                            })
                    
                    print(f" Total access control tasks: {len(all_tasks)}")
                    
                    results = []
                    with ThreadPoolExecutor(max_workers=len(all_tasks)) as task_executor:
                        futures = []
                        for task in all_tasks:
                            future = task_executor.submit(
                                process_device_parallel,
                                task["device"],
                                {"name": task["user"]["name"], "gender": task["user"]["gender"]},
                                task["access"],
                                task["card_no"],
                                task["user_id"],
                                task["user_email"],
                                task["user_type"]
                            )
                            futures.append(future)
                        
                        for future in futures:
                            try:
                                result = future.result(timeout=30)
                                if result and result.get("success"):
                                    results.append(result)
                            except Exception as e:
                                print(f" Task failed: {str(e)}")
                    
                    if results:
                        db_session = SessionLocal()
                        try:
                            for result in results:
                                insert_query = text("""
                                    INSERT INTO resident_device_assign 
                                    (user_id, employee_no, device_id, device_ip, name, gender, 
                                     building_id, valid, door_right, right_plan, local_ui_right, 
                                     max_open_door_time, user_verify_mode, floor_numbers, 
                                     call_numbers, password, created_at, updated_at)
                                    VALUES 
                                    (:user_id, :employee_no, :device_id, :device_ip, :name, :gender,
                                     :building_id, :valid, :door_right, :right_plan, :local_ui_right,
                                     :max_open_door_time, :user_verify_mode, :floor_numbers,
                                     :call_numbers, :password, :created_at, :updated_at)
                                    ON DUPLICATE KEY UPDATE
                                    employee_no = VALUES(employee_no),
                                    valid = VALUES(valid),
                                    updated_at = VALUES(updated_at)
                                """)
                                
                                db_session.execute(insert_query, {
                                    "user_id": result["user_id"],
                                    "employee_no": result["employee_no"],
                                    "device_id": result["device_id"],
                                    "device_ip": result["device_ip"],
                                    "name": result["name"],
                                    "gender": result["gender"],
                                    "building_id": result["building_id"],
                                    "valid": json.dumps(result["valid"]),
                                    "door_right": result["door_right"],
                                    "right_plan": json.dumps(result["right_plan"]),
                                    "local_ui_right": result["local_ui_right"],
                                    "max_open_door_time": result["max_open_door_time"],
                                    "user_verify_mode": result["user_verify_mode"],
                                    "floor_numbers": json.dumps(result["floor_numbers"]),
                                    "call_numbers": json.dumps(result["call_numbers"]),
                                    "password": result["password"],
                                    "created_at": datetime.now(),
                                    "updated_at": datetime.now()
                                })
                                
                                print(f" Stored in DB: User {result['user_id']} -> Device {result['device_ip']}")
                            
                            db_session.commit()
                            print(f" Successfully stored {len(results)} device assignments")
                        except Exception as e:
                            print(f"Error storing device assignments: {str(e)}")
                            db_session.rollback()
                        finally:
                            db_session.close()
                    else:
                        print(" No successful device assignments to store")
                
                background_tasks.add_task(process_all_devices_and_users)
            
            if anpr_devices and created_plates:
                def process_license_plates_to_devices():
                    from DB.db import SessionLocal
                    from requests.auth import HTTPDigestAuth
                    from datetime import datetime
                    
                    print(f"\n Starting license plate sync to {len(anpr_devices)} ANPR devices for {len(created_plates)} plates...")
                    
                    begin_time = access["access_start"]
                    end_time = access["access_end"]
                    
                    if "T" not in begin_time:
                        begin_time = f"{begin_time}T00:00:00"
                    if "T" not in end_time:
                        end_time = f"{end_time}T23:59:59"
                    
                    print(f"  Time range for device: {begin_time} to {end_time}")
                    
                    for plate in created_plates:
                        print(f"\n Processing license plate: {plate['license_plate']} (ListType: {plate['listType']})")
                        
                        plate_info = {
                            "LicensePlate": plate["license_plate"],
                            "cardID": plate["iu_number"],  
                            "cardNo": plate["iu_number"],
                            "certificateNumber": "",
                            "certificateType": "ID",
                            "building_id": access["building_id"],
                            "resident_id": main_user_id,
                            "vehicle_type": plate.get("vehicle_type", "car"),
                            "listType": plate["listType"],
                            "name": "",
                            "operation": "new",
                            "operationType": "add",
                            "plateColor": "blue",
                            "plateDescription": "",
                            "plateType": "92TypeCivil",
                            "virtualParkingNum": "",
                            "createTime": begin_time if plate["listType"] != "blockList" else None,
                            "effectiveTime": end_time if plate["listType"] != "blockList" else None
                        }
                        
                        print(f"  Plate times for device - createTime: {plate_info['createTime']}, effectiveTime: {plate_info['effectiveTime']}")
                        
                        uploaded_devices = []
                        failed_devices = []
                        
                        for device in anpr_devices:
                            device_ip = device["DEVICE_IP"]
                            username = device["USERNAME"]
                            encrypted_password = device["PASSWORD"]
                            
                            print(f"  Uploading to device: {device_ip}")
                            
                            try:
                                password = decrypt_password(encrypted_password)
                                
                                success = upload_license_plate_info(device_ip, username, password, plate_info)
                                
                                if success:
                                    uploaded_devices.append(device_ip)
                                    print(f"   Successfully uploaded to {device_ip}")
                                else:
                                    failed_devices.append(device_ip)
                                    print(f"  Failed to upload to {device_ip}")
                                    
                            except Exception as e:
                                print(f"   Error uploading to {device_ip}: {str(e)}")
                                failed_devices.append(device_ip)
                        
                        if uploaded_devices or failed_devices:
                            db_session = SessionLocal()
                            try:
                                device_activity = {
                                    "uploaded_devices": uploaded_devices,
                                    "failed_devices": failed_devices,
                                    "total_devices": len(anpr_devices),
                                    "timestamp": datetime.now().isoformat(),
                                    "createTime": plate_info["createTime"],
                                    "effectiveTime": plate_info["effectiveTime"]
                                }
                                
                                update_query = text("""
                                    UPDATE license_plate_access 
                                    SET anpr_device_activities = :device_activity,
                                        updated_at = :updated_at
                                    WHERE LicensePlate = :license_plate 
                                    AND resident_id = :resident_id
                                """)
                                db_session.execute(update_query, {
                                    "device_activity": json.dumps(device_activity),
                                    "updated_at": datetime.now(),
                                    "license_plate": plate["license_plate"],
                                    "resident_id": main_user_id
                                })
                                
                                db_session.commit()
                                print(f"  Updated database for plate {plate['license_plate']}")
                                
                            except Exception as e:
                                print(f"  Error updating database: {str(e)}")
                                db_session.rollback()
                            finally:
                                db_session.close()
                        
                        print(f"   Summary for {plate['license_plate']}: Uploaded to {len(uploaded_devices)}/{len(anpr_devices)} devices")
                    
                    print(f"\n ANPR license plate sync completed!")
                
                background_tasks.add_task(process_license_plates_to_devices)

        return {
            "status": 201,
            "message": f" Main user and {len(sub_user_ids)} sub-user(s) created. Syncing {len(all_users_for_devices)} users to {len(devices)} devices and {len(created_plates)} plates to {len(anpr_devices)} ANPR devices in background.",
            "main_user_id": main_user_id,
            "otp": otp,
            "otp_expiry": otp_expiry.isoformat(),
            "devices_count": len(devices) if access else 0,
            "anpr_devices_count": len(anpr_devices) if access else 0,
            "users_count": len(all_users_for_devices),
            "total_tasks": len(all_users_for_devices) * len(devices) if access else 0,
            "user_details": {
                "id": main_user_id,
                "first_name": data["first_name"],
                "last_name": data["last_name"],
                "email": data["email"],
                "card_no": card_no
            },
            "sub_users": created_sub_users,
            "total_sub_users": len(sub_user_ids),
            "license_plates": created_plates,
            "total_license_plates": len(created_plates),
            "devices": [
                {
                    "id": device["device_id"],
                    "ip": device["DEVICE_IP"],
                    "name": device.get("device_name", "Unknown")
                } for device in devices
            ] if access else [],
            "anpr_devices": [
                {
                    "id": device["device_id"],
                    "ip": device["DEVICE_IP"],
                    "name": device.get("device_name", "Unknown")
                } for device in anpr_devices
            ] if access else [],
            "creator_info": {
                "id": creator_id,
                "email": creator_email,
                "name": creator_name,
                "company_id": creator_company_id
            }
        }

    except IntegrityError as ie:
        db.rollback()
        error_detail = f"Integrity error: {str(ie)}"
        
        # Log the error
        try:
            log_user_id = creator_id if 'creator_id' in locals() and creator_id is not None else 1
            
            log_activity(
                db=db,
                user_id=log_user_id,
                action="Create Resident Failed",
                module_name="Resident",
                description=f"Resident creation failed due to integrity error",
                new_data={
                    "payload": {
                        "email": data.get("email") if 'data' in locals() else None,
                        "first_name": data.get("first_name") if 'data' in locals() else None,
                        "last_name": data.get("last_name") if 'data' in locals() else None
                    },
                    "error": str(ie),
                    "creator_info": {
                        "creator_id": creator_id if 'creator_id' in locals() else None,
                        "creator_email": creator_email if 'creator_email' in locals() else None,
                        "creator_name": creator_name if 'creator_name' in locals() else "Unknown",
                        "creator_company_id": creator_company_id if 'creator_company_id' in locals() else None
                    }
                },
                ip_address=ip_address if 'ip_address' in locals() else "Unknown"
            )
        except Exception as log_error:
            print(f"Failed to log integrity error: {log_error}")
        
        if "Duplicate entry" in str(ie.orig) and "email" in str(ie.orig):
            raise HTTPException(status_code=400, detail="Email already exists")
        elif "license_plate" in str(ie.orig).lower():
            raise HTTPException(status_code=400, detail="License plate already exists")
        else:
            raise HTTPException(status_code=400, detail=error_detail)
            
    except HTTPException as he:
        db.rollback()
        
        # Log HTTP exception
        try:
            log_user_id = creator_id if 'creator_id' in locals() and creator_id is not None else 1
            
            log_activity(
                db=db,
                user_id=log_user_id,
                action="Create Resident Failed",
                module_name="Resident",
                description=f"Resident creation failed: {he.detail}",
                new_data={
                    "payload": {
                        "email": data.get("email") if 'data' in locals() else None,
                        "first_name": data.get("first_name") if 'data' in locals() else None
                    },
                    "error": he.detail,
                    "creator_info": {
                        "creator_id": creator_id if 'creator_id' in locals() else None,
                        "creator_email": creator_email if 'creator_email' in locals() else None,
                        "creator_name": creator_name if 'creator_name' in locals() else "Unknown",
                        "creator_company_id": creator_company_id if 'creator_company_id' in locals() else None
                    }
                },
                ip_address=ip_address if 'ip_address' in locals() else "Unknown"
            )
        except Exception as log_error:
            print(f"Failed to log HTTP exception: {log_error}")
        
        raise he
        
    except Exception as e:
        db.rollback()
        print(f"Error details: {str(e)}")
        
        # Log unexpected error
        try:
            import traceback
            full_traceback = traceback.format_exc()
            
            log_user_id = creator_id if 'creator_id' in locals() and creator_id is not None else 1
            
            log_activity(
                db=db,
                user_id=log_user_id,
                action="Create Resident Failed",
                module_name="Resident",
                description=f"Unexpected error while creating resident record",
                new_data={
                    "payload": {
                        "email": data.get("email") if 'data' in locals() else "Unknown",
                        "first_name": data.get("first_name") if 'data' in locals() else "Unknown"
                    },
                    "error": str(e),
                    "traceback": full_traceback,
                    "creator_info": {
                        "creator_id": creator_id if 'creator_id' in locals() else None,
                        "creator_email": creator_email if 'creator_email' in locals() else None,
                        "creator_name": creator_name if 'creator_name' in locals() else "Unknown",
                        "creator_company_id": creator_company_id if 'creator_company_id' in locals() else None
                    }
                },
                ip_address=ip_address if 'ip_address' in locals() else "Unknown"
            )
        except Exception as log_error:
            print(f"Failed to log error activity: {log_error}")
        
        raise HTTPException(status_code=500, detail=f"Insert failed: {str(e)}")




@router.put("/update_resident/{user_id}")
async def update_resident(user_id: int, request: Request, db: Session = Depends(get_db)):
    try:
        now = datetime.now()

        try:
            data = await request.json()
            print("DEBUG update_resident: Parsed as JSON")
        except Exception:
            form = await request.form()
            data = dict(form)
            print("DEBUG update_resident: Parsed as FORM-DATA")

        print("DEBUG Incoming Payload:", data)

        user_exists = db.execute(
            text("SELECT id FROM user_personal_details WHERE id = :id"),
            {"id": user_id}
        ).scalar()

        if not user_exists:
            raise HTTPException(status_code=404, detail=f"User with id {user_id} not found")

        personal_query = text("""
            UPDATE user_personal_details
            SET first_name = COALESCE(:first_name, first_name),
                middle_name = COALESCE(:middle_name, middle_name),
                last_name = COALESCE(:last_name, last_name),
                email = COALESCE(:email, email),
                dob = COALESCE(:dob, dob),
                gender = COALESCE(:gender, gender),
                nationality = COALESCE(:nationality, nationality),
                identity_number = COALESCE(:identity_number, identity_number),
                phone = COALESCE(:phone, phone),
                country_code = COALESCE(:country_code, country_code),
                address = COALESCE(:address, address),
                country = COALESCE(:country, country),
                city = COALESCE(:city, city),
                zipcode = COALESCE(:zipcode, zipcode),
                updated_at = :updated_at
            WHERE id = :id
        """)
        db.execute(personal_query, {
            "id": user_id,
            "first_name": data.get("first_name"),
            "middle_name": data.get("middle_name"),
            "last_name": data.get("last_name"),
            "email": data.get("email"),
            "dob": data.get("dob"),
            "gender": data.get("gender"),
            "nationality": data.get("nationality"),
            "identity_number": data.get("identity_number"),
            "phone": data.get("phone"),
            "country_code": data.get("country_code"),
            "address": data.get("address"),
            "country": data.get("country"),
            "city": data.get("city"),
            "zipcode": data.get("zipcode"),
            "updated_at": now
        })

        emergency = data.get("emergency_details")
        if emergency:
            emergency_query = text("""
                UPDATE user_emergency
                SET first_name = COALESCE(:first_name, first_name),
                    last_name = COALESCE(:last_name, last_name),
                    email = COALESCE(:email, email),
                    phone = COALESCE(:phone, phone),
                    country_code = COALESCE(:country_code, country_code),
                    gender = COALESCE(:gender, gender),
                    nationality = COALESCE(:nationality, nationality),
                    relationship = COALESCE(:relationship, relationship),
                    updated_at = :updated_at
                WHERE user_id = :user_id
            """)
            db.execute(emergency_query, {
                "user_id": user_id,
                "first_name": emergency.get("first_name"),
                "last_name": emergency.get("last_name"),
                "email": emergency.get("email"),
                "phone": emergency.get("phone"),
                "country_code": emergency.get("country_code"),
                "gender": emergency.get("gender"),
                "nationality": emergency.get("nationality"),
                "relationship": emergency.get("relationship"),
                "updated_at": now
            })

        device = db.execute(text("""
            SELECT cd.id AS device_id, cd.ip AS DEVICE_IP, cd.user_name AS USERNAME, cd.password AS PASSWORD
            FROM assign_devices ad
            JOIN camera_devices cd ON ad.device_id = cd.id
            JOIN user_access_details uad ON uad.building_id = ad.building_id
            WHERE uad.user_id = :user_id
            LIMIT 1
        """), {"user_id": user_id}).mappings().fetchone()

        emp_no = db.execute(text("""
            SELECT emp_no FROM device_employee_number WHERE user_id = :user_id
        """), {"user_id": user_id}).scalar()

        if device and emp_no:
            full_name = " ".join(filter(None, [data.get("first_name"), data.get("middle_name"), data.get("last_name")]))
            
            access_details = data.get("access_details", {})
            begin_time_str = access_details.get("beginTime", "2025-09-15 00:00:00")
            end_time_str = access_details.get("endTime", "2035-09-15 23:59:59")

            begin_time_for_device = datetime.fromisoformat(begin_time_str.replace(" ", "T"))
            end_time_for_device = datetime.fromisoformat(end_time_str.replace(" ", "T"))

            person = UpdatePersonRequest(
                user_id=user_id,
                employee_no=emp_no,
                name=full_name,
                gender=data.get("gender", "male"),
                valid=ValidTime(
                    enable=True,
                    beginTime=begin_time_for_device,
                    endTime=end_time_for_device,
                    timeType="local"
                ),
                door_right="1",
                local_ui_right=True,
                max_open_door_time=0,
                user_verify_mode="",
                floor_numbers=[],
                call_numbers=[],
                password=""
            )

            device_response = update_person_in_device(
                person,
                device["DEVICE_IP"],
                device["USERNAME"],
                decrypt_password(device["PASSWORD"])
            )
            print("DEBUG Device Response:", device_response)

            if device_response.get("status") != "success":
                raise Exception(f"Device Update Error: {device_response.get('error')}")

            db_response = update_person_in_db(db, person, device["device_id"])
            if db_response.get("status") != "success":
                raise Exception(f"DB Update Error: {db_response.get('message')}")

        db.commit()

        user = db.execute(text("SELECT * FROM user_personal_details WHERE id = :id"), {"id": user_id}).mappings().fetchone()
        emergency = db.execute(text("SELECT * FROM user_emergency WHERE user_id = :id"), {"id": user_id}).mappings().fetchone()
        access = db.execute(text("SELECT * FROM user_access_details WHERE user_id = :id"), {"id": user_id}).mappings().fetchone()

        return {
            "status": 200,
            "message": "User details updated successfully.",
            "user_id": user_id,
            "user_details": dict(user) if user else {},
            "emergency_details": dict(emergency) if emergency else {},
            "access_details": dict(access) if access else {}
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        print("DEBUG update_resident Exception:", str(e))
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")
    

    
@router.delete("/delete_resident/{user_id}")    
def delete_resident(user_id: int, db: Session = Depends(get_db)):
    try:
        now = datetime.now()

        user = db.execute(
            text("SELECT * FROM user_personal_details WHERE id = :user_id"),
            {"user_id": user_id}
        ).mappings().first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        unit_rows = db.execute(
            text("SELECT unit_id FROM user_access_details WHERE user_id = :user_id"),
            {"user_id": user_id}
        ).mappings().all()

        device_assignments = db.execute(
            text("""
                SELECT rda.employee_no, rda.device_id, cd.ip AS DEVICE_IP, cd.user_name AS USERNAME, cd.password AS PASSWORD
                FROM resident_device_assign rda
                JOIN camera_devices cd ON rda.device_id = cd.id
                WHERE rda.user_id = :user_id
            """),
            {"user_id": user_id}
        ).mappings().all()

        for device_assign in device_assignments:
            if device_assign["employee_no"]:
                print(f"\nDeleting employee_no={device_assign['employee_no']} "
                      f"from device {device_assign['DEVICE_IP']}")

                device_response = delete_person_from_device(
                    employee_no=device_assign["employee_no"],
                    DEVICE_IP=device_assign["DEVICE_IP"],
                    USERNAME=device_assign["USERNAME"],
                    PASSWORD=decrypt_password(device_assign["PASSWORD"])
                )

                if device_response.get("status") != "success":
                    print(f" Device deletion failed for {device_assign['DEVICE_IP']}: {device_response}")
                else:
                    print(f" Deleted from device {device_assign['DEVICE_IP']}")

        db.execute(text("DELETE FROM user_emergency WHERE user_id = :user_id"), {"user_id": user_id})
        db.execute(text("DELETE FROM user_access_details WHERE user_id = :user_id"), {"user_id": user_id})
        db.execute(text("DELETE FROM resident_device_assign WHERE user_id = :user_id"), {"user_id": user_id})
        db.execute(text("DELETE FROM device_employee_number WHERE user_id = :user_id"), {"user_id": user_id})
        db.execute(text("DELETE FROM user_personal_details WHERE id = :user_id"), {"user_id": user_id})

        for unit in unit_rows:
            db.execute(
                text("UPDATE building_units SET disabled = 'false' WHERE id = :unit_id"),
                {"unit_id": unit["unit_id"]}
            )

        db.commit()

        return {
            "status": 200,
            "message": f"Resident deleted successfully from assigned devices and unit unlocked",
            "deleted_at": now.isoformat()
        }

    except HTTPException as he:
        db.rollback()
        raise he
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")
    

@router.post("/send_otp")
def send_existing_otp(request: EmailRequest, db: Session = Depends(get_db)):
    email = request.email
    query = text("""
        SELECT * FROM user_personal_details 
        WHERE email = :email 
        LIMIT 1
    """)
    user = db.execute(query, {"email": email}).mappings().first()

    if not user:
        raise HTTPException(status_code=404, detail="Email does not exist.")

    if user.get("is_verified"):
        return {
            "status": 400,
            "message": "User is already verified. Please proceed to sign in.",
            "user_id": user["id"]
        }

    otp = user["otp"] or generate_otp()
    expiry_time = datetime.now(IST) + timedelta(minutes=15)

    update_query = text("""
        UPDATE user_personal_details 
        SET otp = :otp,
            otp_expiry = :otp_expiry,
            updated_at = NOW()
        WHERE id = :user_id
    """)
    db.execute(update_query, {
        "otp": otp,
        "otp_expiry": expiry_time,
        "user_id": user["id"]
    })
    db.commit()

    send_otp_email(
        email=user["email"],
        first_name=user["first_name"] or "Resident",
        otp=otp,
        resend=False   
    )

    return {
        "status": 200,
        "message": "OTP sent successfully.",
        "otp": otp,
        "otp_expiry": expiry_time.isoformat(),
        "user_id": user["id"]
    }

    
@router.post("/verify_otp")
def verify_otp(payload: OTPVerifyRequest, db: Session = Depends(get_db)):
    try:
        user = db.execute(text("""
            SELECT id, otp, otp_expiry
            FROM user_personal_details
            WHERE email = :email
        """), {"email": payload.email}).mappings().fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user["otp"] != payload.otp:
            raise HTTPException(status_code=400, detail="Invalid OTP")

        otp_expiry = user["otp_expiry"]
        if isinstance(otp_expiry, str):
            otp_expiry = datetime.fromisoformat(otp_expiry)

        if datetime.now() > otp_expiry:
            raise HTTPException(status_code=400, detail="OTP has expired")

        db.execute(text("""
            UPDATE user_personal_details
            SET otp = NULL, otp_expiry = NULL, is_verified = TRUE, updated_at = NOW()
            WHERE id = :id
        """), {"id": user["id"]})

        db.commit()

        return {"status": 200, "message": "OTP verified successfully"}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")
    
@router.post("/verify_email")
def verify_email(request: EmailVerifyRequest, db: Session = Depends(get_db)):
    query = text("""
        SELECT id, is_verified FROM user_personal_details
        WHERE email = :email
        LIMIT 1
    """)
    user = db.execute(query, {"email": request.email}).mappings().first()

    if not user:
        raise HTTPException(status_code=404, detail="Email not found.")

    if not user["is_verified"]:
        raise HTTPException(status_code=403, detail="User is not verified yet. Please verify before login.")

    return {
        "status": 200,
        "message": "Email is verified. Please proceed to sign in.",
        "user_id": user["id"]
    }

    
@router.post("/resend_otp")
def resend_otp(payload: ResendOTPRequest, db: Session = Depends(get_db)):
    try:
        user = db.execute(text("""
            SELECT id, first_name, is_verified
            FROM user_personal_details
            WHERE email = :email
        """), {"email": payload.email}).mappings().fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user["is_verified"]:
            raise HTTPException(status_code=400, detail="User already verified")

        new_otp = str(random.randint(100000, 999999))
        expiry_time = datetime.now() + timedelta(minutes=15)

        db.execute(text("""
            UPDATE user_personal_details
            SET otp = :otp, otp_expiry = :expiry
            WHERE email = :email
        """), {
            "otp": new_otp,
            "expiry": expiry_time,
            "email": payload.email
        })
        db.commit()

        result = send_otp_email(payload.email, user["first_name"], new_otp, resend=True)

        if not result or result.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to resend OTP")

        return {"status": 200, "message": "OTP resent successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Resend OTP failed: {str(e)}")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@router.post("/set_password")
def set_password(payload: SetPasswordRequest, db: Session = Depends(get_db)):
    try:
        user = db.execute(text("""
            SELECT id, is_verified FROM user_personal_details WHERE email = :email
        """), {"email": payload.email}).mappings().fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if not user["is_verified"]:
            raise HTTPException(status_code=400, detail="User is not verified yet")

        hashed_password = bcrypt.hash(payload.password)

        db.execute(text("""
            UPDATE user_personal_details
            SET password = :password
            WHERE email = :email
        """), {
            "password": hashed_password,
            "email": payload.email
        })
        db.commit()

        return {"status": 200, "message": "Password set successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/list_resident")
def list_users(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search by name, email, or phone"),
    user_id: Optional[int] = Query(None, description="Filter by specific user_id"),
    id: Optional[int] = Query(None, description="Filter by specific user ID (main user or sub-user)")
):
    try:
        offset = (page - 1) * per_page

        valid_id = None
        if id is not None and id != "" and id != "null" and id != "undefined":
            try:
                valid_id = int(id)
            except (ValueError, TypeError):
                valid_id = None

        valid_user_id = None
        if user_id is not None and user_id != "" and user_id != "null" and user_id != "undefined":
            try:
                valid_user_id = int(user_id)
            except (ValueError, TypeError):
                valid_user_id = None

        filters = []
        params = {}

        if search:
            filters.append(
                "(up.first_name LIKE :search OR up.last_name LIKE :search OR up.email LIKE :search OR up.phone LIKE :search)"
            )
            params["search"] = f"%{search}%"

        if valid_user_id:
            filters.append("up.id = :user_id")
            params["user_id"] = valid_user_id

        specific_user_id = None
        is_sub_user = False
        
        if valid_id:
            check_sub_query = """
                SELECT main_user_id FROM resident_family_members 
                WHERE sub_user_id = :id
            """
            sub_check = db.execute(text(check_sub_query), {"id": valid_id}).fetchone()
            
            if sub_check:
                specific_user_id = sub_check[0]
                is_sub_user = True
            else:
                specific_user_id = valid_id
                is_sub_user = False

        main_query = """
            SELECT 
                up.id,
                up.first_name,
                up.middle_name,
                up.last_name,
                up.email,
                up.phone,
                up.gender,
                up.dob,
                up.nationality,
                up.identity_number,
                up.country_code,
                up.address,
                up.country,
                up.city,
                up.zipcode,
                up.card_no,
                up.created_at,
                up.updated_at,

                ue.first_name AS emergency_first_name,
                ue.last_name AS emergency_last_name,
                ue.email AS emergency_email,
                ue.phone AS emergency_phone,
                ue.gender AS emergency_gender,
                ue.nationality AS emergency_nationality,
                ue.relationship AS emergency_relationship,

                ua.residency_type_id,
                rt.name AS residency_type_name,
                ua.building_id,
                ua.level_id,
                ua.unit_id,
                ua.join_date,
                ua.access_start,
                ua.access_end,

                pb.building_name,
                bl.level AS level_name,
                bu.unit_no AS unit_name,

                rda.name AS device_name,
                rda.gender AS device_gender,
                rda.employee_no,
                rda.image_upload_path

            FROM user_personal_details up
            LEFT JOIN user_emergency ue ON up.id = ue.user_id
            LEFT JOIN user_access_details ua ON up.id = ua.user_id
            LEFT JOIN residency_type rt ON ua.residency_type_id = rt.id
            LEFT JOIN property_building pb ON ua.building_id = pb.id
            LEFT JOIN building_level bl ON ua.level_id = bl.id
            LEFT JOIN building_units bu ON ua.unit_id = bu.id
            LEFT JOIN resident_device_assign rda ON up.id = rda.user_id
            LEFT JOIN resident_family_members rfm ON up.id = rfm.sub_user_id
            WHERE rfm.sub_user_id IS NULL
        """

        if specific_user_id:
            filters.append("up.id = :specific_user_id")
            params["specific_user_id"] = specific_user_id

        if filters:
            main_query += " AND " + " AND ".join(filters)

        count_query = """
            SELECT COUNT(DISTINCT up.id) 
            FROM user_personal_details up
            LEFT JOIN resident_family_members rfm ON up.id = rfm.sub_user_id
            WHERE rfm.sub_user_id IS NULL
        """
        
        count_params = {}
        count_filters = []
        
        if search:
            count_filters.append(
                "(up.first_name LIKE :search OR up.last_name LIKE :search OR up.email LIKE :search OR up.phone LIKE :search)"
            )
            count_params["search"] = f"%{search}%"
        
        if valid_user_id:
            count_filters.append("up.id = :user_id")
            count_params["user_id"] = valid_user_id
        
        if specific_user_id:
            count_filters.append("up.id = :specific_user_id")
            count_params["specific_user_id"] = specific_user_id
        
        if count_filters:
            count_query += " AND " + " AND ".join(count_filters)
        
        total_count = db.execute(text(count_query), count_params).scalar() or 0
        last_page = (total_count + per_page - 1) // per_page if total_count > 0 else 1

        if not specific_user_id:
            main_query += " ORDER BY up.id DESC LIMIT :limit OFFSET :offset"
            params.update({"limit": per_page, "offset": offset})
        else:
            main_query += " ORDER BY up.id DESC"
            page = 1
            per_page = 1

        main_users = db.execute(text(main_query), params).mappings().all()

        result_data = []
        for main_user in main_users:
            main_user_dict = dict(main_user)
            
            sub_users_query = """
                SELECT 
                    up.id,
                    up.first_name,
                    up.middle_name,
                    up.last_name,
                    up.email,
                    up.phone,
                    up.gender,
                    up.dob,
                    up.nationality,
                    up.identity_number,
                    up.country_code,
                    up.address,
                    up.country,
                    up.city,
                    up.zipcode,
                    up.card_no,
                    up.created_at,
                    up.updated_at,
                    rfm.relationship,
                    rfm.is_primary,
                    
                    ua.residency_type_id,
                    rt.name AS residency_type_name,
                    ua.building_id,
                    ua.level_id,
                    ua.unit_id,
                    ua.join_date,
                    ua.access_start,
                    ua.access_end,
                    
                    pb.building_name,
                    bl.level AS level_name,
                    bu.unit_no AS unit_name,
                    
                    rda.name AS device_name,
                    rda.gender AS device_gender,
                    rda.employee_no,
                    rda.image_upload_path
                    
                FROM user_personal_details up
                INNER JOIN resident_family_members rfm ON up.id = rfm.sub_user_id
                LEFT JOIN user_access_details ua ON up.id = ua.user_id
                LEFT JOIN residency_type rt ON ua.residency_type_id = rt.id
                LEFT JOIN property_building pb ON ua.building_id = pb.id
                LEFT JOIN building_level bl ON ua.level_id = bl.id
                LEFT JOIN building_units bu ON ua.unit_id = bu.id
                LEFT JOIN resident_device_assign rda ON up.id = rda.user_id
                WHERE rfm.main_user_id = :main_user_id
                ORDER BY up.id ASC
            """
            
            sub_users = db.execute(text(sub_users_query), {"main_user_id": main_user_dict["id"]}).mappings().all()
            main_user_dict["sub_users"] = [dict(sub_user) for sub_user in sub_users]
            
            if is_sub_user and valid_id:
                main_user_dict["sub_users"] = [su for su in main_user_dict["sub_users"] if su["id"] == valid_id]
            
            vehicles_query = """
                SELECT 
                    lpa.id,
                    lpa.LicensePlate AS license_plate,
                    lpa.vehicle_type,
                    vt.title AS vehicle_type_title,
                    lpa.iu_number,
                    lpa.listType,
                    lpa.createTime,
                    lpa.effectiveTime,
                    lpa.anpr_device_activities,
                    lpa.created_at,
                    lpa.updated_at,
                    lpa.source AS vehicle_owner_type,
                    vc.no_of_vehicle_free_slot,
                    vc.Amount AS vehicle_charge_amount
                FROM license_plate_access lpa
                LEFT JOIN vehicle_type vt ON lpa.vehicle_type = vt.id
                LEFT JOIN vehicle_configurations vc ON vt.id = vc.vehicle_type_id
                WHERE lpa.resident_id = :user_id
                ORDER BY lpa.created_at DESC
            """
            
            vehicles = db.execute(text(vehicles_query), {"user_id": main_user_dict["id"]}).mappings().all()
            
            vehicles_list = []
            for vehicle in vehicles:
                vehicle_dict = dict(vehicle)
                vehicle_dict["vehicle_type"] = vehicle_dict.get("vehicle_type_title")
                
                if "vehicle_type_title" in vehicle_dict:
                    del vehicle_dict["vehicle_type_title"]
                
                vehicle_dict["vehicle_configuration"] = {
                    "free_slots": vehicle_dict.get("no_of_vehicle_free_slot", "0"),
                    "charge_amount": vehicle_dict.get("vehicle_charge_amount", "0")
                }
                
                if "no_of_vehicle_free_slot" in vehicle_dict:
                    del vehicle_dict["no_of_vehicle_free_slot"]
                if "vehicle_charge_amount" in vehicle_dict:
                    del vehicle_dict["vehicle_charge_amount"]
                
                vehicles_list.append(vehicle_dict)
            
            main_user_dict["vehicles"] = vehicles_list
            
            result_data.append(main_user_dict)

        # Handle sub-user case when no result found
        if valid_id and not result_data and is_sub_user:
            sub_user_query = """
                SELECT 
                    up.id,
                    up.first_name,
                    up.middle_name,
                    up.last_name,
                    up.email,
                    up.phone,
                    up.gender,
                    up.dob,
                    up.nationality,
                    up.identity_number,
                    up.country_code,
                    up.address,
                    up.country,
                    up.city,
                    up.zipcode,
                    up.card_no,
                    up.created_at,
                    up.updated_at,
                    rfm.relationship,
                    rfm.main_user_id,
                    
                    ua.residency_type_id,
                    rt.name AS residency_type_name,
                    ua.building_id,
                    ua.level_id,
                    ua.unit_id,
                    ua.join_date,
                    ua.access_start,
                    ua.access_end,
                    
                    pb.building_name,
                    bl.level AS level_name,
                    bu.unit_no AS unit_name,
                    
                    rda.name AS device_name,
                    rda.gender AS device_gender,
                    rda.employee_no,
                    rda.image_upload_path
                    
                FROM user_personal_details up
                INNER JOIN resident_family_members rfm ON up.id = rfm.sub_user_id
                LEFT JOIN user_access_details ua ON up.id = ua.user_id
                LEFT JOIN residency_type rt ON ua.residency_type_id = rt.id
                LEFT JOIN property_building pb ON ua.building_id = pb.id
                LEFT JOIN building_level bl ON ua.level_id = bl.id
                LEFT JOIN building_units bu ON ua.unit_id = bu.id
                LEFT JOIN resident_device_assign rda ON up.id = rda.user_id
                WHERE up.id = :sub_user_id
            """
            
            sub_user = db.execute(text(sub_user_query), {"sub_user_id": valid_id}).mappings().first()
            if sub_user:
                main_user_for_sub = db.execute(
                    text("SELECT * FROM user_personal_details WHERE id = :main_id"),
                    {"main_id": sub_user["main_user_id"]}
                ).mappings().first()
                
                if main_user_for_sub:
                    main_dict = dict(main_user_for_sub)
                    main_dict["sub_users"] = [dict(sub_user)]
                    main_dict["vehicles"] = []
                    
                    vehicles_query = """
                        SELECT 
                            lpa.id,
                            lpa.LicensePlate AS license_plate,
                            lpa.vehicle_type,
                            vt.title AS vehicle_type_title,
                            lpa.iu_number,
                            lpa.listType,
                            lpa.createTime,
                            lpa.effectiveTime,
                            lpa.anpr_device_activities,
                            lpa.created_at,
                            lpa.updated_at,
                            lpa.source AS vehicle_owner_type,
                            vc.no_of_vehicle_free_slot,
                            vc.Amount AS vehicle_charge_amount
                        FROM license_plate_access lpa
                        LEFT JOIN vehicle_type vt ON lpa.vehicle_type = vt.id
                        LEFT JOIN vehicle_configurations vc ON vt.id = vc.vehicle_type_id
                        WHERE lpa.resident_id = :user_id
                        ORDER BY lpa.created_at DESC
                    """
                    
                    vehicles = db.execute(
                        text(vehicles_query),
                        {"user_id": main_dict["id"]}
                    ).mappings().all()
                    
                    vehicles_list = []
                    for vehicle in vehicles:
                        vehicle_dict = dict(vehicle)
                        vehicle_dict["vehicle_type"] = vehicle_dict.get("vehicle_type_title")
                        
                        if "vehicle_type_title" in vehicle_dict:
                            del vehicle_dict["vehicle_type_title"]
                        
                        vehicle_dict["vehicle_configuration"] = {
                            "free_slots": vehicle_dict.get("no_of_vehicle_free_slot", "0"),
                            "charge_amount": vehicle_dict.get("vehicle_charge_amount", "0")
                        }
                        
                        if "no_of_vehicle_free_slot" in vehicle_dict:
                            del vehicle_dict["no_of_vehicle_free_slot"]
                        if "vehicle_charge_amount" in vehicle_dict:
                            del vehicle_dict["vehicle_charge_amount"]
                        
                        vehicles_list.append(vehicle_dict)
                    
                    main_dict["vehicles"] = vehicles_list
                    result_data.append(main_dict)

        return {
            "status": 200,
            "message": "User list fetched successfully.",
            "data": result_data,
            "pagination_details": {
                "page": page,
                "per_page": per_page,
                "total": total_count,
                "last_page": last_page
            },
            "filter_info": {
                "search": search,
                "user_id": valid_user_id,
                "id": valid_id,
                "is_sub_user": is_sub_user if valid_id else None
            }
        }

    except Exception as e:
        print(f"Error in list_users: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch users: {str(e)}")



    
@router.get("/resident_analysis")
def resident_analysis(
    year: int = Query(..., description="Year to analyze"),
    db: Session = Depends(get_db)
):
    try:
        resident_query = text("""
            SELECT 
                MONTH(created_at) AS month,
                COUNT(*) AS user_count
            FROM user_personal_details
            WHERE YEAR(created_at) = :year
            GROUP BY MONTH(created_at)
            ORDER BY month
        """)
        resident_result = db.execute(resident_query, {"year": year}).mappings().all()

        # Modified: Only invite_visitor table (removed adoc_visitor)
        visitor_query = text("""
            SELECT 
                MONTH(created_at) AS month,
                COUNT(*) AS visitor_count
            FROM invite_visitor
            WHERE YEAR(created_at) = :year
            GROUP BY MONTH(created_at)
            ORDER BY month
        """)
        visitor_result = db.execute(visitor_query, {"year": year}).mappings().all()

        camera_query = text("""
            SELECT 
                MONTH(created_date) AS month,
                COUNT(*) AS camera_count
            FROM camera_devices
            WHERE YEAR(created_date) = :year
            GROUP BY MONTH(created_date)
            ORDER BY month
        """)
        camera_result = db.execute(camera_query, {"year": year}).mappings().all()

        # Modified: Using license_plate_access table instead of license_plate_access_assign
        license_query = text("""
            SELECT 
                MONTH(created_at) AS month,
                COUNT(*) AS license_count
            FROM license_plate_access
            WHERE YEAR(created_at) = :year
            GROUP BY MONTH(created_at)
            ORDER BY month
        """)
        license_result = db.execute(license_query, {"year": year}).mappings().all()

        building_query = text("""
            SELECT 
                MONTH(created_at) AS month,
                COUNT(*) AS building_count
            FROM property_building
            WHERE YEAR(created_at) = :year
            GROUP BY MONTH(created_at)
            ORDER BY month
        """)
        building_result = db.execute(building_query, {"year": year}).mappings().all()

        # Total device count from camera_devices (all time, not filtered by year)
        total_devices_query = text("""
            SELECT COUNT(*) AS total_devices
            FROM camera_devices
        """)
        total_devices = db.execute(total_devices_query).scalar()

        month_names = {
            1: "jan", 2: "feb", 3: "mar", 4: "apr",
            5: "may", 6: "jun", 7: "jul", 8: "aug",
            9: "sep", 10: "oct", 11: "nov", 12: "dec"
        }

        resident_monthly = {name: 0 for name in month_names.values()}
        visitor_monthly = {name: 0 for name in month_names.values()}
        camera_monthly = {name: 0 for name in month_names.values()}
        license_monthly = {name: 0 for name in month_names.values()}
        building_monthly = {name: 0 for name in month_names.values()}

        for row in resident_result:
            resident_monthly[month_names[row["month"]]] = row["user_count"]

        for row in visitor_result:
            visitor_monthly[month_names[row["month"]]] = row["visitor_count"]

        for row in camera_result:
            camera_monthly[month_names[row["month"]]] = row["camera_count"]

        for row in license_result:
            license_monthly[month_names[row["month"]]] = row["license_count"]

        for row in building_result:
            building_monthly[month_names[row["month"]]] = row["building_count"]

        resident_overall = sum(resident_monthly.values())
        visitor_overall = sum(visitor_monthly.values())
        camera_overall = sum(camera_monthly.values())
        license_overall = sum(license_monthly.values())
        building_overall = sum(building_monthly.values())

        return {
            "status": 200,
            "message": f"Analysis for year {year}",
            "year": year,
            "resident_analysis": {
                "monthly_counts": resident_monthly,
                "overall_count": resident_overall
            },
            "visitor_analysis": {
                "monthly_counts": visitor_monthly,
                "overall_count": visitor_overall
            },
            "camera_analysis": {
                "monthly_counts": camera_monthly,
                "overall_count": camera_overall,
                "total_devices": total_devices  # Added total_devices inside camera_analysis
            },
            "license_analysis": {
                "monthly_counts": license_monthly,
                "overall_count": license_overall
            },
            "building_analysis": {
                "monthly_counts": building_monthly,
                "overall_count": building_overall
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch analysis: {str(e)}")



    
@router.get("/list_resident_filter")
def list_users(db: Session = Depends(get_db)):
    try:
        query = text("""
            SELECT 
                up.id AS id,
                up.first_name,
                up.email,
                up.phone,
                ua.building_id

            FROM user_personal_details up
            LEFT JOIN user_emergency ue ON up.id = ue.user_id
            LEFT JOIN user_access_details ua ON up.id = ua.user_id
            LEFT JOIN residency_type rt ON ua.residency_type_id = rt.id
            LEFT JOIN resident_device_assign rda ON up.id = rda.user_id
        """)

        result = db.execute(query).mappings().all()
        return {
            "status": 200,
            "message": "User list fetched successfully.",
            "data": [dict(row) for row in result]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch users: {str(e)}")



@router.post("/resident_login")
def login_user(payload: LoginRequest, db: Session = Depends(get_db)):
    try:
        check_user = db.execute(text("""
            SELECT * FROM user_personal_details WHERE email = :email
        """), {"email": payload.email}).mappings().first()

        if not check_user:
            raise HTTPException(status_code=404, detail="User with this email not found.")

        if not bcrypt.verify(payload.password, check_user["password"]):
            raise HTTPException(status_code=401, detail="Incorrect password.")
        
        if not check_user["is_verified"]:
            raise HTTPException(status_code=403, detail="Please verify your email before logging in.")
        
        access_token, expires_at, issued_at = create_access_token(data={"sub": check_user["email"]})

        if payload.fcm_token:
            db.execute(text("""
                UPDATE user_personal_details
                SET fcm_token = :fcm_token
                WHERE id = :user_id
            """), {"fcm_token": payload.fcm_token, "user_id": check_user["id"]})

        db.execute(text("""
            UPDATE user_personal_details
            SET is_active = 2
            WHERE id = :user_id
        """), {"user_id": check_user["id"]})

        db.commit()

        query = text("""
            SELECT 
                up.id AS id,
                up.first_name,
                up.middle_name,
                up.last_name,
                up.email,
                up.phone,
                up.gender,
                up.dob,
                up.nationality,
                up.identity_number,
                up.country_code,
                up.address,
                up.country,
                up.city,
                up.zipcode,
                up.created_at,
                up.updated_at,

                ue.first_name AS emergency_first_name,
                ue.last_name AS emergency_last_name,
                ue.email AS emergency_email,
                ue.phone AS emergency_phone,
                ue.gender AS emergency_gender,
                ue.nationality AS emergency_nationality,
                ue.relationship,

                ua.residency_type_id,
                rt.name as resident_name,
                ua.building_id,
                ua.level_id,
                ua.unit_id,
                ua.join_date,
                ua.access_start,
                ua.access_end,
                up.fcm_token,
                up.card_no,  

                rda.name,
                rda.gender,
                rda.employee_no,
                rda.image_upload_path,

                pb.building_name AS building_name,
                pl.level AS level_name,
                bu.unit_no AS unit_name,

                up.is_active  -- include is_active in response
            FROM user_personal_details up
            LEFT JOIN user_emergency ue ON up.id = ue.user_id
            LEFT JOIN user_access_details ua ON up.id = ua.user_id
            LEFT JOIN residency_type rt ON ua.residency_type_id = rt.id
            LEFT JOIN resident_device_assign rda ON up.id = rda.user_id
            LEFT JOIN property_building pb ON ua.building_id = pb.id
            LEFT JOIN  building_level pl ON ua.level_id = pl.id
            LEFT JOIN building_units bu ON ua.unit_id = bu.id

            WHERE up.email = :email
        """)

        result = db.execute(query, {"email": payload.email}).mappings().first()

        if not result:
            raise HTTPException(status_code=404, detail="User data not found.")

        result_dict = dict(result)

        if result_dict.get("join_date") and isinstance(result_dict["join_date"], (date, datetime)):
            result_dict["join_date"] = result_dict["join_date"].strftime("%d-%m-%Y")

        if result_dict.get("access_start") and isinstance(result_dict["access_start"], (date, datetime)):
            result_dict["access_start"] = result_dict["access_start"].strftime("%d-%m-%Y")

        if result_dict.get("access_end") and isinstance(result_dict["access_end"], (date, datetime)):
            result_dict["access_end"] = result_dict["access_end"].strftime("%d-%m-%Y")

        return {
            "status": 200,
            "message": "Login successful.",
            "access_token": access_token,
            "data": result_dict
        }

    except HTTPException:
        raise  
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed due to internal error: {str(e)}")

@router.post("/resident_logout")
def logout_user(payload: LogoutRequest, db: Session = Depends(get_db)):
    try:
        user = db.execute(text("""
            SELECT id FROM user_personal_details WHERE id = :user_id
        """), {"user_id": payload.user_id}).mappings().first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        db.execute(text("""
            UPDATE user_personal_details
            SET is_active = 1
            WHERE id = :user_id
        """), {"user_id": payload.user_id})
        db.commit()

        return {
            "status": 201,
            "message": "Logout successful."
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Logout failed: {str(e)}")

@router.put("/update_user_personal_details/{user_id}", dependencies=[Depends(verify_token)])
async def update_user_personal_details(user_id: int, request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()

        update_query = text("""
            UPDATE user_personal_details
            SET first_name = :first_name,
                middle_name = :middle_name,
                last_name = :last_name,
                email = :email,
                dob = :dob,
                gender = :gender,
                nationality = :nationality,
                identity_number = :identity_number,
                phone = :phone,
                country_code = :country_code,
                address = :address,
                country = :country,
                city = :city,
                updated_date = :updated_date,
                zipcode = :zipcode
            WHERE id = :id
        """)

        result = db.execute(update_query, {
            "id": user_id,
            "first_name": data["first_name"],
            "middle_name": data.get("middle_name"),
            "last_name": data["last_name"],
            "email": data["email"],
            "dob": data.get("dob"),
            "gender": data.get("gender"),
            "nationality": data.get("nationality"),
            "identity_number": data.get("identity_number"),
            "phone": data.get("phone"),
            "country_code": data.get("country_code"),
            "address": data.get("address"),
            "country": data.get("country"),
            "city": data.get("city"),
            "zipcode": data.get("zipcode"),
        })

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="User personal details not found.")

        db.commit()
        return {
            "status": 200,
            "message": "User personal details updated successfully.",
        }

    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")


@router.get("/list_invoice_details")
def list_invoice_detail(
    db: Session = Depends(get_db),
    search: Optional[str] = Query(None, description="Search by name, email, or phone"),
    user_id: Optional[int] = Query(None, description="Filter by specific user_id"),
    id: Optional[int] = Query(None, description="Filter by specific user ID (main user or sub-user)")
):
    try:
        from datetime import datetime
        import calendar
        from decimal import Decimal, ROUND_DOWN
        
        valid_id = None
        if id is not None and id != "" and id != "null" and id != "undefined":
            try:
                valid_id = int(id)
            except (ValueError, TypeError):
                valid_id = None

        valid_user_id = None
        if user_id is not None and user_id != "" and user_id != "null" and user_id != "undefined":
            try:
                valid_user_id = int(user_id)
            except (ValueError, TypeError):
                valid_user_id = None

        filters = []
        params = {}

        if search:
            filters.append(
                "(up.first_name LIKE :search OR up.last_name LIKE :search OR up.email LIKE :search OR up.phone LIKE :search)"
            )
            params["search"] = f"%{search}%"

        if valid_user_id:
            filters.append("up.id = :user_id")
            params["user_id"] = valid_user_id

        specific_user_id = None
        is_sub_user = False
        
        if valid_id:
            check_sub_query = """
                SELECT main_user_id FROM resident_family_members 
                WHERE sub_user_id = :id
            """
            sub_check = db.execute(text(check_sub_query), {"id": valid_id}).fetchone()
            
            if sub_check:
                specific_user_id = sub_check[0]
                is_sub_user = True
            else:
                specific_user_id = valid_id
                is_sub_user = False

        main_query = """
            SELECT 
                up.id,
                up.first_name,
                up.middle_name,
                up.last_name,
                up.email,
                up.phone,
                up.gender,
                up.dob,
                up.nationality,
                up.identity_number,
                up.country_code,
                up.address,
                up.country,
                up.city,
                up.zipcode,
                up.card_no,
                up.created_at,
                up.updated_at,

                ue.first_name AS emergency_first_name,
                ue.last_name AS emergency_last_name,
                ue.email AS emergency_email,
                ue.phone AS emergency_phone,
                ue.gender AS emergency_gender,
                ue.nationality AS emergency_nationality,
                ue.relationship AS emergency_relationship,

                ua.residency_type_id,
                rt.name AS residency_type_name,
                ua.building_id,
                ua.level_id,
                ua.unit_id,
                ua.join_date,
                ua.access_start,
                ua.access_end,

                pb.building_name,
                bl.level AS level_name,
                bu.unit_no AS unit_name,

                rda.name AS device_name,
                rda.gender AS device_gender,
                rda.employee_no,
                rda.image_upload_path

            FROM user_personal_details up
            LEFT JOIN user_emergency ue ON up.id = ue.user_id
            LEFT JOIN user_access_details ua ON up.id = ua.user_id
            LEFT JOIN residency_type rt ON ua.residency_type_id = rt.id
            LEFT JOIN property_building pb ON ua.building_id = pb.id
            LEFT JOIN building_level bl ON ua.level_id = bl.id
            LEFT JOIN building_units bu ON ua.unit_id = bu.id
            LEFT JOIN resident_device_assign rda ON up.id = rda.user_id
            LEFT JOIN resident_family_members rfm ON up.id = rfm.sub_user_id
            WHERE rfm.sub_user_id IS NULL
        """

        if specific_user_id:
            filters.append("up.id = :specific_user_id")
            params["specific_user_id"] = specific_user_id

        if filters:
            main_query += " AND " + " AND ".join(filters)

        main_query += " ORDER BY up.id DESC"

        main_users = db.execute(text(main_query), params).mappings().all()

        result_data = []
        for main_user in main_users:
            main_user_dict = dict(main_user)
            
            sub_users_query = """
                SELECT 
                    up.id,
                    up.first_name,
                    up.middle_name,
                    up.last_name,
                    up.email,
                    up.phone,
                    up.gender,
                    up.dob,
                    up.nationality,
                    up.identity_number,
                    up.country_code,
                    up.address,
                    up.country,
                    up.city,
                    up.zipcode,
                    up.card_no,
                    up.created_at,
                    up.updated_at,
                    rfm.relationship,
                    rfm.is_primary,
                    
                    ua.residency_type_id,
                    rt.name AS residency_type_name,
                    ua.building_id,
                    ua.level_id,
                    ua.unit_id,
                    ua.join_date,
                    ua.access_start,
                    ua.access_end,
                    
                    pb.building_name,
                    bl.level AS level_name,
                    bu.unit_no AS unit_name,
                    
                    rda.name AS device_name,
                    rda.gender AS device_gender,
                    rda.employee_no,
                    rda.image_upload_path
                    
                FROM user_personal_details up
                INNER JOIN resident_family_members rfm ON up.id = rfm.sub_user_id
                LEFT JOIN user_access_details ua ON up.id = ua.user_id
                LEFT JOIN residency_type rt ON ua.residency_type_id = rt.id
                LEFT JOIN property_building pb ON ua.building_id = pb.id
                LEFT JOIN building_level bl ON ua.level_id = bl.id
                LEFT JOIN building_units bu ON ua.unit_id = bu.id
                LEFT JOIN resident_device_assign rda ON up.id = rda.user_id
                WHERE rfm.main_user_id = :main_user_id
                ORDER BY up.id ASC
            """
            
            sub_users = db.execute(text(sub_users_query), {"main_user_id": main_user_dict["id"]}).mappings().all()
            main_user_dict["sub_users"] = [dict(sub_user) for sub_user in sub_users]
            
            if is_sub_user and valid_id:
                main_user_dict["sub_users"] = [su for su in main_user_dict["sub_users"] if su["id"] == valid_id]
            
            # Updated vehicles query with amount calculation
# Updated vehicles query with correct date calculation
            vehicles_query = """
    SELECT 
        lpa.id AS vehicle_id,
        lpa.LicensePlate AS license_plate,
        lpa.vehicle_type,
        vt.title AS vehicle_type_title,
        lpa.iu_number,
        lpa.listType,
        lpa.source AS vehicle_owner_type,
        CAST(vc.Amount AS DECIMAL(10,2)) AS base_amount,
        vc.billing_period,
        vc.no_of_vehicle_free_slot,

        COALESCE(
            (
                SELECT 
                    SUM(
                        CASE 
                            -- For completed stays (has exit_time)
                            WHEN aa.exit_time IS NOT NULL AND aa.exit_time != '' THEN 
                                GREATEST(
                                    DATEDIFF(
                                        DATE(SUBSTRING_INDEX(aa.exit_time, 'T', 1)),
                                        DATE(SUBSTRING_INDEX(aa.entry_time, 'T', 1))
                                    ) + 1,
                                    1
                                )
                            -- For ongoing stay (no exit_time, still inside)
                            WHEN aa.entry_time IS NOT NULL AND aa.entry_time != '' THEN 
                                GREATEST(
                                    DATEDIFF(
                                        CURDATE(),
                                        DATE(SUBSTRING_INDEX(aa.entry_time, 'T', 1))
                                    ) + 1,
                                    1
                                )
                            ELSE 0
                        END
                    )
                FROM anpr_device_activities aa
                WHERE JSON_UNQUOTE(JSON_EXTRACT(aa.anpr_device_activity, '$.plate_number')) = lpa.LicensePlate
                    AND aa.resident_id = CAST(lpa.resident_id AS CHAR)
                    AND aa.entry_time IS NOT NULL 
                    AND aa.entry_time != ''
                    AND (
                        -- For completed stays
                        (aa.exit_time IS NOT NULL AND aa.exit_time != '')
                        OR 
                        -- For ongoing stay (no exit time)
                        (aa.exit_time IS NULL OR aa.exit_time = '')
                    )
            ),
            0
        ) AS no_of_days
        
    FROM license_plate_access lpa
    LEFT JOIN vehicle_type vt ON lpa.vehicle_type = vt.id
    LEFT JOIN vehicle_configurations vc ON vt.id = vc.vehicle_type_id
    WHERE lpa.resident_id = :user_id
    ORDER BY lpa.created_at DESC
"""
            
            vehicles = db.execute(text(vehicles_query), {"user_id": main_user_dict["id"]}).mappings().all()
            
            vehicles_list = []
            for vehicle in vehicles:
                # Get values with proper type conversion
                base_amount_str = vehicle.get('base_amount')
                if base_amount_str is None or base_amount_str == '':
                    base_amount = 0.0
                else:
                    try:
                        base_amount = float(base_amount_str)
                    except (ValueError, TypeError):
                        base_amount = 0.0
                
                billing_period_raw = vehicle.get('billing_period', 'daily')
                no_of_days = vehicle.get('no_of_days') or 0
                vehicle_owner_type_raw = vehicle.get('vehicle_owner_type', 'visitor')
                
                # Capitalize vehicle_owner_type
                vehicle_owner_type = vehicle_owner_type_raw.capitalize() if vehicle_owner_type_raw else 'Visitor'
                
                # Capitalize billing period
                billing_period = billing_period_raw.capitalize() if billing_period_raw else 'Daily'
                
                # Convert no_of_days to int if it's a string
                try:
                    no_of_days = int(no_of_days)
                except (ValueError, TypeError):
                    no_of_days = 0
                
                calculated_amount = 0.0
                per_day_amount = 0.0
                
                # Different calculation logic for residents vs visitors
                if vehicle_owner_type_raw == 'resident':
                    # RESIDENT: Full payment based on billing period
                    if billing_period_raw == 'daily':
                        # Daily: amount per day
                        per_day_amount = base_amount
                        calculated_amount = base_amount * no_of_days
                    elif billing_period_raw == 'monthly':
                        # Monthly: full monthly amount (not prorated)
                        per_day_amount = base_amount / 30
                        calculated_amount = base_amount
                    elif billing_period_raw == 'yearly':
                        # Yearly: full yearly amount (not prorated)
                        current_year = datetime.now().year
                        days_in_year = 366 if calendar.isleap(current_year) else 365
                        per_day_amount = base_amount / days_in_year
                        calculated_amount = base_amount
                    else:
                        per_day_amount = base_amount
                        calculated_amount = base_amount
                        
                else:  # VISITOR: Prorated based on actual days used
                    if billing_period_raw == 'daily':
                        # Daily: amount * number of days
                        per_day_amount = base_amount
                        calculated_amount = base_amount * no_of_days
                        
                    elif billing_period_raw == 'monthly':
                        # Monthly: calculate daily rate and multiply by days
                        now = datetime.now()
                        if now.month == 2:  # February
                            current_month_days = 29 if calendar.isleap(now.year) else 28
                        elif now.month in [4, 6, 9, 11]:  # 30-day months
                            current_month_days = 30
                        else:  # 31-day months
                            current_month_days = 31
                        
                        if current_month_days > 0:
                            # Calculate with Decimal for precise arithmetic
                            base_decimal = Decimal(str(base_amount))
                            days_decimal = Decimal(str(current_month_days))
                            no_of_days_decimal = Decimal(str(no_of_days))
                            
                            per_day_decimal = base_decimal / days_decimal
                            # Round per_day_amount to 2 decimal places (floor/truncate)
                            per_day_decimal = per_day_decimal.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
                            per_day_amount = float(per_day_decimal)
                            
                            # Calculate total without rounding - use exact multiplication
                            calculated_decimal = per_day_decimal * no_of_days_decimal
                            # Keep as is without rounding, just show 2 decimal places
                            calculated_amount = float(calculated_decimal)
                        else:
                            per_day_amount = 0
                            calculated_amount = 0
                        
                    elif billing_period_raw == 'yearly':
                        # Yearly: calculate daily rate and multiply by days
                        current_year = datetime.now().year
                        days_in_year = 366 if calendar.isleap(current_year) else 365
                        
                        if days_in_year > 0:
                            # Calculate with Decimal for precise arithmetic
                            base_decimal = Decimal(str(base_amount))
                            days_decimal = Decimal(str(days_in_year))
                            no_of_days_decimal = Decimal(str(no_of_days))
                            
                            per_day_decimal = base_decimal / days_decimal
                            # Round per_day_amount to 2 decimal places (floor/truncate)
                            per_day_decimal = per_day_decimal.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
                            per_day_amount = float(per_day_decimal)
                            
                            # Calculate total without rounding - use exact multiplication
                            calculated_decimal = per_day_decimal * no_of_days_decimal
                            # Keep as is without rounding, just show 2 decimal places
                            calculated_amount = float(calculated_decimal)
                        else:
                            per_day_amount = 0
                            calculated_amount = 0
                    else:
                        per_day_amount = 0
                        calculated_amount = 0
                
                # Format to 2 decimal places without rounding
                per_day_amount_display = "{:.2f}".format(per_day_amount)
                calculated_amount_display = "{:.2f}".format(calculated_amount)
                
                vehicle_dict = {
                     "vehicle_id": vehicle['vehicle_id'],
                    "license_plate": vehicle['license_plate'],
                    "vehicle_type_id": vehicle['vehicle_type'],
                    "vehicle_type": vehicle['vehicle_type_title'] if vehicle['vehicle_type_title'] else vehicle['vehicle_type'],
                   
                    "iu_number": vehicle['iu_number'],
                    "listType": vehicle['listType'],
                    "vehicle_owner_type": vehicle_owner_type,
                    "no_of_days": no_of_days,
                    "base_amount": round(base_amount, 2),
                    "billing_period": billing_period,
                    "per_day_amount": float(per_day_amount_display),
                    "calculated_amount": float(calculated_amount_display)
                }
                vehicles_list.append(vehicle_dict)
            
            main_user_dict["vehicles"] = vehicles_list
            
            result_data.append(main_user_dict)

        # Handle sub-user case when no result found
        if valid_id and not result_data and is_sub_user:
            sub_user_query = """
                SELECT 
                    up.id,
                    up.first_name,
                    up.middle_name,
                    up.last_name,
                    up.email,
                    up.phone,
                    up.gender,
                    up.dob,
                    up.nationality,
                    up.identity_number,
                    up.country_code,
                    up.address,
                    up.country,
                    up.city,
                    up.zipcode,
                    up.card_no,
                    up.created_at,
                    up.updated_at,
                    rfm.relationship,
                    rfm.main_user_id,
                    
                    ua.residency_type_id,
                    rt.name AS residency_type_name,
                    ua.building_id,
                    ua.level_id,
                    ua.unit_id,
                    ua.join_date,
                    ua.access_start,
                    ua.access_end,
                    
                    pb.building_name,
                    bl.level AS level_name,
                    bu.unit_no AS unit_name,
                    
                    rda.name AS device_name,
                    rda.gender AS device_gender,
                    rda.employee_no,
                    rda.image_upload_path
                    
                FROM user_personal_details up
                INNER JOIN resident_family_members rfm ON up.id = rfm.sub_user_id
                LEFT JOIN user_access_details ua ON up.id = ua.user_id
                LEFT JOIN residency_type rt ON ua.residency_type_id = rt.id
                LEFT JOIN property_building pb ON ua.building_id = pb.id
                LEFT JOIN building_level bl ON ua.level_id = bl.id
                LEFT JOIN building_units bu ON ua.unit_id = bu.id
                LEFT JOIN resident_device_assign rda ON up.id = rda.user_id
                WHERE up.id = :sub_user_id
            """
            
            sub_user = db.execute(text(sub_user_query), {"sub_user_id": valid_id}).mappings().first()
            if sub_user:
                main_user_for_sub = db.execute(
                    text("SELECT * FROM user_personal_details WHERE id = :main_id"),
                    {"main_id": sub_user["main_user_id"]}
                ).mappings().first()
                
                if main_user_for_sub:
                    main_dict = dict(main_user_for_sub)
                    main_dict["sub_users"] = [dict(sub_user)]
                    
                    # Updated vehicles query for sub-user case with amount calculation
                    vehicles_query = """
    SELECT 
        lpa.id AS vehicle_id, 
        lpa.LicensePlate AS license_plate,
        lpa.vehicle_type,
        vt.title AS vehicle_type_title,
        lpa.iu_number,
        lpa.listType,
        lpa.source AS vehicle_owner_type,
        CAST(vc.Amount AS DECIMAL(10,2)) AS base_amount,
        vc.billing_period,
        vc.no_of_vehicle_free_slot,
        
        COALESCE(
            (
                SELECT 
                    CASE 
                        -- If vehicle has exited, calculate days between entry and exit (date only)
                        WHEN aa.exit_time IS NOT NULL AND aa.exit_time != '' THEN 
                            GREATEST(
                                DATEDIFF(
                                    DATE(SUBSTRING_INDEX(aa.exit_time, 'T', 1)),
                                    DATE(SUBSTRING_INDEX(aa.entry_time, 'T', 1))
                                ) + 1,
                                1
                            )
                        -- If vehicle is still inside (no exit time), calculate from entry to today (date only)
                        WHEN aa.entry_time IS NOT NULL AND aa.entry_time != '' THEN 
                            GREATEST(
                                DATEDIFF(
                                    CURDATE(),
                                    DATE(SUBSTRING_INDEX(aa.entry_time, 'T', 1))
                                ) + 1,
                                1
                            )
                        ELSE 0
                    END
                FROM anpr_device_activities aa
                WHERE JSON_UNQUOTE(JSON_EXTRACT(aa.anpr_device_activity, '$.plate_number')) = lpa.LicensePlate
                    AND aa.resident_id = CAST(lpa.resident_id AS CHAR)
                    AND aa.entry_time IS NOT NULL 
                    AND aa.entry_time != ''
                ORDER BY aa.id DESC
                LIMIT 1
            ),
            0
        ) AS no_of_days
        
    FROM license_plate_access lpa
    LEFT JOIN vehicle_type vt ON lpa.vehicle_type = vt.id
    LEFT JOIN vehicle_configurations vc ON vt.id = vc.vehicle_type_id
    WHERE lpa.resident_id = :user_id
    ORDER BY lpa.created_at DESC
"""
                    
                    vehicles = db.execute(
                        text(vehicles_query),
                        {"user_id": main_dict["id"]}
                    ).mappings().all()
                    
                    vehicles_list = []
                    for vehicle in vehicles:
                        # Get values with proper type conversion
                        base_amount_str = vehicle.get('base_amount')
                        if base_amount_str is None or base_amount_str == '':
                            base_amount = 0.0
                        else:
                            try:
                                base_amount = float(base_amount_str)
                            except (ValueError, TypeError):
                                base_amount = 0.0
                        
                        billing_period_raw = vehicle.get('billing_period', 'daily')
                        no_of_days = vehicle.get('no_of_days') or 0
                        vehicle_owner_type_raw = vehicle.get('vehicle_owner_type', 'visitor')
                        
                        # Capitalize vehicle_owner_type
                        vehicle_owner_type = vehicle_owner_type_raw.capitalize() if vehicle_owner_type_raw else 'Visitor'
                        
                        # Capitalize billing period
                        billing_period = billing_period_raw.capitalize() if billing_period_raw else 'Daily'
                        
                        # Convert no_of_days to int if it's a string
                        try:
                            no_of_days = int(no_of_days)
                        except (ValueError, TypeError):
                            no_of_days = 0
                        
                        calculated_amount = 0.0
                        per_day_amount = 0.0
                        
                        # Different calculation logic for residents vs visitors
                        if vehicle_owner_type_raw == 'resident':
                            # RESIDENT: Full payment based on billing period
                            if billing_period_raw == 'daily':
                                per_day_amount = base_amount
                                calculated_amount = base_amount * no_of_days
                            elif billing_period_raw == 'monthly':
                                per_day_amount = base_amount / 30
                                calculated_amount = base_amount
                            elif billing_period_raw == 'yearly':
                                current_year = datetime.now().year
                                days_in_year = 366 if calendar.isleap(current_year) else 365
                                per_day_amount = base_amount / days_in_year
                                calculated_amount = base_amount
                            else:
                                per_day_amount = base_amount
                                calculated_amount = base_amount
                                
                        else:  # VISITOR: Prorated based on actual days used
                            if billing_period_raw == 'daily':
                                per_day_amount = base_amount
                                calculated_amount = base_amount * no_of_days
                                
                            elif billing_period_raw == 'monthly':
                                now = datetime.now()
                                if now.month == 2:
                                    current_month_days = 29 if calendar.isleap(now.year) else 28
                                elif now.month in [4, 6, 9, 11]:
                                    current_month_days = 30
                                else:
                                    current_month_days = 31
                                
                                if current_month_days > 0:
                                    # Calculate with Decimal for precise arithmetic
                                    base_decimal = Decimal(str(base_amount))
                                    days_decimal = Decimal(str(current_month_days))
                                    no_of_days_decimal = Decimal(str(no_of_days))
                                    
                                    per_day_decimal = base_decimal / days_decimal
                                    # Round per_day_amount to 2 decimal places (floor/truncate)
                                    per_day_decimal = per_day_decimal.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
                                    per_day_amount = float(per_day_decimal)
                                    
                                    # Calculate total without rounding - use exact multiplication
                                    calculated_decimal = per_day_decimal * no_of_days_decimal
                                    # Keep as is without rounding, just show 2 decimal places
                                    calculated_amount = float(calculated_decimal)
                                else:
                                    per_day_amount = 0
                                    calculated_amount = 0
                                
                            elif billing_period_raw == 'yearly':
                                current_year = datetime.now().year
                                days_in_year = 366 if calendar.isleap(current_year) else 365
                                
                                if days_in_year > 0:
                                    # Calculate with Decimal for precise arithmetic
                                    base_decimal = Decimal(str(base_amount))
                                    days_decimal = Decimal(str(days_in_year))
                                    no_of_days_decimal = Decimal(str(no_of_days))
                                    
                                    per_day_decimal = base_decimal / days_decimal
                                    # Round per_day_amount to 2 decimal places (floor/truncate)
                                    per_day_decimal = per_day_decimal.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
                                    per_day_amount = float(per_day_decimal)
                                    
                                    # Calculate total without rounding - use exact multiplication
                                    calculated_decimal = per_day_decimal * no_of_days_decimal
                                    # Keep as is without rounding, just show 2 decimal places
                                    calculated_amount = float(calculated_decimal)
                                else:
                                    per_day_amount = 0
                                    calculated_amount = 0
                            else:
                                per_day_amount = 0
                                calculated_amount = 0
                        
                        # Format to 2 decimal places without rounding
                        per_day_amount_display = "{:.2f}".format(per_day_amount)
                        calculated_amount_display = "{:.2f}".format(calculated_amount)
                        
                        vehicle_dict = {
                             "vehicle_id": vehicle['vehicle_id'],
                            "license_plate": vehicle['license_plate'],
                            "vehicle_type_id": vehicle['vehicle_type'],
                            "vehicle_type": vehicle['vehicle_type_title'] if vehicle['vehicle_type_title'] else vehicle['vehicle_type'],
                            "iu_number": vehicle['iu_number'],
                            "listType": vehicle['listType'],
                            "vehicle_owner_type": vehicle_owner_type,
                            "no_of_days": no_of_days,
                            "base_amount": round(base_amount, 2),
                            "billing_period": billing_period,
                            "per_day_amount": float(per_day_amount_display),
                            "calculated_amount": float(calculated_amount_display)
                        }
                        vehicles_list.append(vehicle_dict)
                    
                    main_dict["vehicles"] = vehicles_list
                    result_data.append(main_dict)

        return {
            "status": 200,
            "message": "User list fetched successfully.",
            "data": result_data,
            "filter_info": {
                "search": search,
                "user_id": valid_user_id,
                "id": valid_id,
                "is_sub_user": is_sub_user if valid_id else None
            }
        }

    except Exception as e:
        print(f"Error in list_users: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch users: {str(e)}")


@router.get("/get_public_key")
def get_public_key():
    """Provides the RSA public key to the frontend."""
    from utils.security import get_rsa_public_key
    public_key = get_rsa_public_key()
    if not public_key:
        raise HTTPException(status_code=500, detail="Public key not found.")
    return {"public_key": public_key}