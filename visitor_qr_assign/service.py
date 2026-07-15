import os
import uuid
import requests
import urllib3
import random
import string
import io
import base64
import qrcode
from typing import Optional
from datetime import datetime, timedelta
import json
from fastapi import APIRouter, Depends, HTTPException,Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from requests.auth import HTTPDigestAuth
from .models import DeviceRequest
from DB.db import get_db
from fastapi import Query
from utils.security import decrypt_password
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from utils.common_function import generate_card_number,generate_visitor_id
from a_visitor.service import create_visitor_profile,upload_qr_card
from utils.security import encrypt_card_no
from utils.common_function import generate_unique_qr_token
from anpr_camera_assign.service import upload_license_plate_info
from utils.common_function import BASE_URL

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))



# def upload_qr_card(device_ip, username, password,
#                    visitor_id, card_no, valid_from, valid_to):
#     url = f"http://{device_ip}/ISAPI/AccessControl/CardInfo/Record?format=json"
#     payload = {
#         "CardInfo": {
#             "employeeNo": visitor_id,
#             "cardNo": card_no,
#             "cardType": "normalCard",
#             "status": "active",
#             "doorRight": "10",
#             "valid": {
#                 "enable": True,
#                 "beginTime": valid_from,
#                 "endTime": valid_to
#             }
#         }
#     }

#     res = requests.post(url, auth=requests.auth.HTTPDigestAuth(username, password),
#                         json=payload, verify=False)
#     return res.status_code == 200, res.text


@router.post("/create_visitor_by_user")
def create_visitor(payload: DeviceRequest, db: Session = Depends(get_db)):
    try:
        print(f"\n=== CREATE VISITOR REQUEST ===")
        print(f"Payload received: {payload.dict()}")
        
        device_result = db.execute(text("""
            SELECT device_id 
            FROM resident_device_assign 
            WHERE user_id = :user_id
        """), {"user_id": payload.user_id}).mappings().first()

        if not device_result:
            raise HTTPException(status_code=404, detail="No device assigned to this user.")

        device_id = device_result["device_id"]
        print(f"Device ID found: {device_id}")

        camera_result = db.execute(text("""
            SELECT ip, user_name, password 
            FROM camera_devices 
            WHERE id = :device_id
        """), {"device_id": device_id}).mappings().first()

        if not camera_result:
            raise HTTPException(status_code=404, detail="Device not found in camera_devices.")

        device_ip = camera_result["ip"]
        username = camera_result["user_name"]
        password = decrypt_password(camera_result["password"])
        print(f"Device IP: {device_ip}")

        visitor_id = generate_visitor_id()
        card_no = generate_card_number()   
        qr_token = generate_unique_qr_token(db)
        print(f"Generated - Visitor ID: {visitor_id}, Card No: {card_no}, QR Token: {qr_token}")
        
        phone_number = getattr(payload, "phone", None)
        print(f"Phone number: {phone_number}")
        
        iu_number = getattr(payload, "iu_number", None)
        print(f"IU Number from payload: {iu_number}")

        if not getattr(payload, "valid_from", None) or not getattr(payload, "valid_to", None):
            raise HTTPException(status_code=400, detail="valid_from and valid_to are required.")

        valid_from_date = datetime.strptime(payload.valid_from, "%Y-%m-%d").date()
        valid_from_dt = datetime.combine(valid_from_date, datetime.now().time())

        valid_to_date = datetime.strptime(payload.valid_to, "%Y-%m-%d").date()
        valid_to_dt = datetime.combine(valid_to_date, datetime.max.time()).replace(microsecond=0)

        valid_from = valid_from_dt.strftime("%Y-%m-%dT%H:%M:%S")
        valid_to = valid_to_dt.strftime("%Y-%m-%dT%H:%M:%S")
        print(f"Validity - From: {valid_from}, To: {valid_to}")

        gender = getattr(payload, "gender", None) or "unknown"

        success_profile, profile_response = create_visitor_profile(
            device_ip,
            username,
            password,
            visitor_id,
            payload.visitor_name,
            gender,
            valid_from,
            valid_to
        )

        if not success_profile:
            raise HTTPException(
                status_code=400,
                detail=f"Visitor profile upload failed: {profile_response}"
            )
        print("Visitor profile uploaded successfully")

        success_card, card_response = upload_qr_card(
            device_ip,
            username,
            password,
            visitor_id,
            card_no,   
            valid_from,
            valid_to
        )

        if not success_card:
            raise HTTPException(
                status_code=400,
                detail=f"QR card upload failed: {card_response}"
            )
        print("QR card uploaded successfully")

        db.execute(text("""
            INSERT INTO invite_visitor (
                name,
                user_id,
                visitor_id,
                purpose_visit,
                card_no,
                phone,
                valid,
                qr_token,
                created_at,
                updated_at
            ) VALUES (
                :name,
                :user_id,
                :visitor_id,
                :purpose_visit,
                :card_no,
                :phone,
                :valid,
                :qr_token,
                NOW(),
                NOW()
            )
        """), {
            "name": payload.visitor_name,
            "user_id": payload.user_id,
            "visitor_id": visitor_id,
            "purpose_visit": getattr(payload, "purpose_of_visitor", None),
            "card_no": card_no,
            "phone": phone_number,  
            "valid": json.dumps({
                "beginTime": valid_from,
                "endTime": valid_to
            }),
            "qr_token": qr_token
        })
        print("Visitor stored in invite_visitor table")

        qr_url = f"{BASE_URL}/view_qr_image/{qr_token}"
        print(f"QR URL generated: {qr_url}")

        license_plate_id = None
        print(f"\n=== CHECKING LICENSE PLATE CONDITIONS ===")
        print(f"vehicle_type present: {hasattr(payload, 'vehicle_type') and payload.vehicle_type}")
        print(f"building_id present: {hasattr(payload, 'building_id') and payload.building_id}")
        print(f"vehicle_type value: {getattr(payload, 'vehicle_type', None)}")
        print(f"building_id value: {getattr(payload, 'building_id', None)}")
        
        if hasattr(payload, 'vehicle_type') and payload.vehicle_type and hasattr(payload, 'building_id') and payload.building_id:
            print("\n=== PROCESSING LICENSE PLATE ===")
            
            if hasattr(payload, 'license_plate') and payload.license_plate:
                license_plate = payload.license_plate
                print(f"Using provided license plate: {license_plate}")
            else:
                license_plate = f"VISITOR_{visitor_id[:8]}"
                print(f"Generated license plate: {license_plate}")
            
            final_iu_number = iu_number 
            print(f"IU Number to be used: {final_iu_number}")
            
            create_time_db = payload.valid_from
            effective_time_db = payload.valid_to
            print(f"Database times - Create: {create_time_db}, Effective: {effective_time_db}")
            
            insert_plate_query = text("""
                INSERT INTO license_plate_access (
                    LicensePlate,
                    building_id,
                    resident_id,
                    iu_number,
                    listType,
                    vehicle_type,
                    createTime,
                    effectiveTime,
                    source,
                    created_at,
                    updated_at
                ) VALUES (
                    :license_plate,
                    :building_id,
                    :resident_id,
                    :iu_number,
                    :list_type,
                    :vehicle_type,
                    :create_time,
                    :effective_time,
                    :source,
                    NOW(),
                    NOW()
                )
            """)
            
            result = db.execute(insert_plate_query, {
                "license_plate": license_plate,
                "building_id": payload.building_id,
                "resident_id": int(payload.user_id),
                "iu_number": final_iu_number,
                "list_type": "allowList",
                "vehicle_type": str(payload.vehicle_type),
                "create_time": create_time_db,
                "effective_time": effective_time_db,
                "source": "visitor",
            })
            
            license_plate_id = result.lastrowid if hasattr(result, 'lastrowid') else db.execute(text("SELECT LAST_INSERT_ID()")).scalar()
            print(f"License plate inserted with ID: {license_plate_id}")

            print("\n=== UPLOADING TO ANPR DEVICES ===")
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
            """), {"building_id": payload.building_id}).mappings().fetchall()
            
            print(f"Building ANPR devices found: {len(anpr_devices)}")
            
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
            
            print(f"Common ANPR devices found: {len(common_anpr_devices)}")
            
            all_anpr_devices = list(anpr_devices) + list(common_anpr_devices)
            
            if all_anpr_devices:
                print(f"Total ANPR devices: {len(all_anpr_devices)}")
                
                plate_info = {
                    "LicensePlate": license_plate,
                    "cardID": final_iu_number,
                    "cardNo": final_iu_number,
                    "certificateNumber": "",
                    "certificateType": "ID",
                    "building_id": payload.building_id,
                    "resident_id": int(payload.user_id),
                    "vehicle_type": str(payload.vehicle_type),
                    "listType": "allowList",
                    "name": payload.visitor_name,
                    "operation": "new",
                    "operationType": "add",
                    "plateColor": "blue",
                    "plateDescription": "",
                    "plateType": "92TypeCivil",
                    "virtualParkingNum": "",
                    "createTime": valid_from,
                    "effectiveTime": valid_to
                }
                
                print(f"Plate info prepared: {plate_info}")
                
                uploaded_devices = []
                failed_devices = []
                
                for device in all_anpr_devices:
                    device_ip_anpr = device["DEVICE_IP"]
                    username_anpr = device["USERNAME"]
                    encrypted_password_anpr = device["PASSWORD"]
                    
                    print(f"\nUploading to ANPR device: {device_ip_anpr}")
                    
                    try:
                        password_anpr = decrypt_password(encrypted_password_anpr)
                        
                        success = upload_license_plate_info(
                            device_ip_anpr, 
                            username_anpr, 
                            password_anpr, 
                            plate_info
                        )
                        
                        if success:
                            uploaded_devices.append(device_ip_anpr)
                            print(f"  SUCCESS: Uploaded to {device_ip_anpr}")
                        else:
                            failed_devices.append(device_ip_anpr)
                            print(f"  FAILED: Could not upload to {device_ip_anpr}")
                            
                    except Exception as e:
                        print(f"  ERROR: {str(e)}")
                        failed_devices.append(device_ip_anpr)
                
                if uploaded_devices or failed_devices:
                    device_activity = {
                        "uploaded_devices": uploaded_devices,
                        "failed_devices": failed_devices,
                        "total_devices": len(all_anpr_devices),
                        "timestamp": datetime.now().isoformat(),
                        "visitor_name": payload.visitor_name,
                        "visitor_id": visitor_id
                    }
                    
                    update_query = text("""
                        UPDATE license_plate_access 
                        SET anpr_device_activities = :device_activity,
                            updated_at = NOW()
                        WHERE id = :plate_id
                    """)
                    db.execute(update_query, {
                        "device_activity": json.dumps(device_activity),
                        "plate_id": license_plate_id
                    })
                    
                    print(f"\nUpdated ANPR device activities for license plate")
                    print(f"Uploaded to: {uploaded_devices}")
                    print(f"Failed on: {failed_devices}")
            else:
                print("No ANPR devices found for license plate upload")
        else:
            print("\n=== SKIPPING LICENSE PLATE INSERTION ===")
            print("Conditions not met for license plate insertion")

        db.commit()
        print("\n=== TRANSACTION COMMITTED SUCCESSFULLY ===")

        response_data = {
            "status": 200,
            "message": "Visitor and QR card created successfully.",
            "data": {
                "visitor_id": visitor_id,
                "visitor_name": payload.visitor_name,
                "purpose_of_visitor": getattr(payload, "purpose_of_visitor", None),
                "phone": phone_number,  
                "card_no": card_no,  
                "qr_token": qr_token,
                "qr_url": qr_url,  
                "valid_from": valid_from,
                "valid_to": valid_to
            }
        }
        
        if license_plate_id:
            response_data["data"]["license_plate"] = {
                "id": license_plate_id,
                "plate_number": license_plate if 'license_plate' in locals() else None,
                "iu_number": final_iu_number if 'final_iu_number' in locals() else iu_number,
                "vehicle_type": payload.vehicle_type,
                "valid_from": payload.valid_from,
                "valid_to": payload.valid_to
            }
        
        return response_data

    except HTTPException as http_exc:
        db.rollback()
        print(f"HTTP Exception: {http_exc.detail}")
        raise http_exc

    except Exception as e:
        db.rollback()
        print(f"Error details: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

    

@router.get("/visitor_list_by_user/{user_id}")
def get_visitors_by_user(user_id: str, db: Session = Depends(get_db)):
    try:
        query = text("""
            SELECT id, visitor_id, name AS visitor_name,purpose_visit, card_no, valid, created_at
            FROM invite_visitor
            WHERE user_id = :user_id
            ORDER BY created_at DESC
        """)
        results = db.execute(query, {"user_id": user_id}).mappings().all()

        if not results:
            raise HTTPException(status_code=404, detail="No visitors found for this user.")

        visitors = []
        for row in results:
            visitors.append({
                "id":row["id"],
                "visitor_id": row["visitor_id"],
                "visitor_name": row["visitor_name"],
                "card_no": row["card_no"],
                "purpose_visit": row["purpose_visit"],
                # "visit_times": row["visit_times"],
                "valid": json.loads(row["valid"]) if isinstance(row["valid"], str) else row["valid"],
                "created_at": row["created_at"]
            })

        return {
            "status": 200,
            "message": f"Found {len(visitors)} visitor(s)",
            "data": visitors
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching visitors: {str(e)}")
    



@router.get("/visitor_list")
def get_visitors_by_user(
    user_id: Optional[int] = Query(None, description="Filter invite_visitor by this user_id"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1),
    search: Optional[str] = Query(None, alias="searchdata"),
    sort: Optional[str] = Query(None, description="Sort visitors: old = oldest first, recent = most recent first"),
    db: Session = Depends(get_db)
):
    try:
        offset = (page - 1) * limit
        params = {"limit": limit, "offset": offset}

        
        where_invite = ""
        if user_id is not None:
            where_invite = "WHERE inv.user_id = :user_id"
            params["user_id"] = str(user_id)  

        if search:
            search_param = f"%{search}%"
            if where_invite:
                where_invite += " AND inv.name LIKE :search"
            else:
                where_invite = "WHERE inv.name LIKE :search"
            params["search"] = search_param

        where_adoc = ""
        if search:
            where_adoc = "WHERE adoc.name LIKE :search"
            params["search"] = search_param

        
        count_query = text(f"""
            SELECT COUNT(*) FROM (
                SELECT inv.id 
                FROM invite_visitor inv
                {where_invite}
                UNION ALL
                SELECT adoc.id 
                FROM adoc_visitor adoc
                {where_adoc}
            ) AS total_visitors
        """)
        total_count = db.execute(count_query, params).scalar()

        
        sort_order = "ASC" if sort == "old" else "DESC"

        
        query = text(f"""
            -- Visitors from invite_visitor
            SELECT 
                inv.id,
                inv.visitor_id,
                inv.user_id,
                inv.name AS visitor_name,
                inv.card_no,
                NULL AS visit_times,
                inv.valid,
                inv.created_at,
                NULL AS email,
                inv.purpose_visit,
                inv.phone,
                uad.building_id, 
                uad.level_id, 
                uad.unit_id,
                pb.building_name, 
                bl.level AS level_name, 
                bu.unit_no AS unit_name,
                upd.first_name AS invited_by,
                'invite' AS visitor_type
            FROM invite_visitor inv
            LEFT JOIN user_access_details uad ON inv.user_id = uad.user_id
            LEFT JOIN property_building pb ON pb.id = uad.building_id
            LEFT JOIN building_level bl ON bl.id = uad.level_id
            LEFT JOIN building_units bu ON bu.id = uad.unit_id
            LEFT JOIN user_personal_details upd ON upd.id = inv.user_id
            {where_invite}

            UNION ALL

            -- Visitors from adoc_visitor
            SELECT 
                adoc.id,
                NULL AS visitor_id,
                NULL AS user_id,
                adoc.name AS visitor_name,
                adoc.card_no,
                NULL AS visit_times,
                adoc.valid,
                adoc.created_at,
                adoc.email,
                adoc.purpose_visit,
                adoc.phone,
                adoc.building_id, 
                adoc.level_id, 
                adoc.unit_id,
                pb.building_name, 
                bl.level AS level_name, 
                bu.unit_no AS unit_name,
                NULL AS invited_by,
                'adoc' AS visitor_type
            FROM adoc_visitor adoc
            LEFT JOIN property_building pb ON pb.id = adoc.building_id
            LEFT JOIN building_level bl ON bl.id = adoc.level_id
            LEFT JOIN building_units bu ON bu.id = adoc.unit_id
            {where_adoc}

            ORDER BY created_at {sort_order}
            LIMIT :limit OFFSET :offset
        """)
        
        results = db.execute(query, params).mappings().all()

        if not results:
            return {
                "status": 200,
                "message": "No visitors found",
                "page": page,
                "limit": limit,
                "total": 0,
                "total_pages": 0,
                "sort": sort,
                "data": []
            }

        visitors = []
        for row in results:
            
            valid_data = None
            if row.get("valid"):
                if isinstance(row["valid"], str):
                    try:
                        valid_data = json.loads(row["valid"])
                    except:
                        valid_data = row["valid"]
                else:
                    valid_data = row["valid"]
            
            visitor_dict = {
                "id": row["id"],
                "visitor_type": row.get("visitor_type"),
                "visitor_id": row.get("visitor_id", ""),
                "user_id": row.get("user_id"),
                "visitor_name": row["visitor_name"],
                "card_no": row.get("card_no"),
                "visit_times": row.get("visit_times"),
                "valid": valid_data,
                "created_at": row["created_at"].strftime("%Y-%m-%d %H:%M:%S") if row["created_at"] else None,
                "email": row.get("email"),
                "phone": row.get("phone"),
                "building_id": row.get("building_id"),
                "level_id": row.get("level_id"),
                "unit_id": row.get("unit_id"),
                "purpose_visit": row.get("purpose_visit"),
                "building_name": row.get("building_name"),
                "level_name": row.get("level_name"),
                "unit_name": row.get("unit_name"),
                "invited_by": row.get("invited_by")   
            }
            
            
            visitor_dict = {k: v for k, v in visitor_dict.items() if v is not None}
            
            visitors.append(visitor_dict)

        return {
            "status": 200,
            "message": f"Found {len(visitors)} visitor(s)",
            "page": page,
            "limit": limit,
            "total": total_count,
            "total_pages": (total_count + limit - 1) // limit,
            "sort": sort,
            "data": visitors
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error fetching visitors: {str(e)}")




@router.get("/view-qr", response_class=HTMLResponse)
async def view_qr_page(request: Request):
    return templates.TemplateResponse(
        "view_qr_page.html", 
        {"request": request}
    )


# @router.get("/view_qr_image/{qr_token}", response_class=HTMLResponse)
# async def view_qr_by_token(qr_token: str, request: Request, db: Session = Depends(get_db)):
    
#     visitor = db.execute(text("""
#         SELECT 
#             av.name, 
#             av.phone, 
#             av.purpose_visit, 
#             av.card_no, 
#             av.valid, 
#             'adoc' as source,
#             av.building_id,
#             av.level_id,
#             av.unit_id,
#             pb.building_name,
#             bl.level AS level_name,
#             bu.unit_no AS unit_name
#         FROM adoc_visitor av
#         LEFT JOIN property_building pb ON av.building_id = pb.id
#         LEFT JOIN building_level bl ON av.level_id = bl.id
#         LEFT JOIN building_units bu ON av.unit_id = bu.id
#         WHERE av.qr_token = :qr_token
#         ORDER BY av.id DESC
#         LIMIT 1
#     """), {"qr_token": qr_token}).mappings().first()
    

#     if not visitor:
#         visitor = db.execute(text("""
#             SELECT 
#                 iv.name, 
#                 iv.phone, 
#                 iv.purpose_visit, 
#                 iv.card_no, 
#                 iv.valid, 
#                 'invite' as source,
#                 ua.building_id,
#                 ua.level_id,
#                 ua.unit_id,
#                 pb.building_name,
#                 bl.level AS level_name,
#                 bu.unit_no AS unit_name
#             FROM invite_visitor iv
#             LEFT JOIN user_access_details ua ON iv.user_id = ua.user_id
#             LEFT JOIN property_building pb ON ua.building_id = pb.id
#             LEFT JOIN building_level bl ON ua.level_id = bl.id
#             LEFT JOIN building_units bu ON ua.unit_id = bu.id
#             WHERE iv.qr_token = :qr_token
#             ORDER BY iv.id DESC
#             LIMIT 1
#         """), {"qr_token": qr_token}).mappings().first()

#     access_level_parts = []
#     if visitor and visitor.get("building_name"):
#         access_level_parts.append(visitor["building_name"])
#     if visitor and visitor.get("level_name"):
#         access_level_parts.append(f"Level {visitor['level_name']}")
#     if visitor and visitor.get("unit_name"):
#         access_level_parts.append(f"Unit {visitor['unit_name']}")
    
#     access_level_display = " · ".join(access_level_parts) if access_level_parts else "Main Lobby · General Access"

#     context = {
#         "request": request,
#         "is_valid": False,
#         "is_found": bool(visitor),
#         "qr_image": None,
#         "qr_status": "QR expiry",
#         "visitor_name": "",
#         "phone": "",
#         "purpose_visit": "",
#         "valid_until": "N/A",
#         "source": visitor.get("source") if visitor else None,
#         "access_level": access_level_display,
#         "building_name": visitor.get("building_name") if visitor else None,
#         "level_name": visitor.get("level_name") if visitor else None,
#         "unit_name": visitor.get("unit_name") if visitor else None
#     }

#     if not visitor:
#         context["qr_status"] = "Invalid QR token"
#         return templates.TemplateResponse("view_qr_page.html", context)

#     valid_data = visitor["valid"]
#     if isinstance(valid_data, str):
#         try:
#             valid_data = json.loads(valid_data)
#         except Exception:
#             valid_data = {}

#     end_time_str = valid_data.get("endTime")
#     valid_until = end_time_str or "N/A"
#     is_valid = False
    
#     if end_time_str:
#         try:
#             try:
#                 valid_until_dt = datetime.fromisoformat(end_time_str)
#             except:
#                 valid_until_dt = datetime.strptime(end_time_str, "%Y-%m-%d")
            
#             is_valid = datetime.now() <= valid_until_dt
#             valid_until = valid_until_dt.strftime("%d %b %Y %I:%M %p")
#         except Exception as e:
#             print(f"Error parsing date: {e}")
#             valid_until = end_time_str

#     context.update({
#         "visitor_name": visitor.get("name") or "",
#         "phone": visitor.get("phone") or "",
#         "purpose_visit": visitor.get("purpose_visit") or "",
#         "valid_until": valid_until,
#         "source": visitor.get("source")
#     })

#     if is_valid and visitor.get("card_no"):
    
#         qr = qrcode.make(visitor["card_no"])
#         buffer = io.BytesIO()
#         qr.save(buffer, format="PNG")
#         context["qr_image"] = base64.b64encode(buffer.getvalue()).decode("utf-8")
#         context["is_valid"] = True
#         context["qr_status"] = "Scan to Enter"
#     else:
#         context["qr_status"] = "QR Expired or Invalid"

#     return templates.TemplateResponse("view_qr_page.html", context)
@router.get("/view_qr_image/{qr_token}", response_class=HTMLResponse)
async def view_qr_by_token(qr_token: str, request: Request, db: Session = Depends(get_db)):

    visitor = db.execute(text("""
        SELECT 
            av.name, 
            av.phone, 
            av.purpose_visit, 
            av.card_no, 
            av.valid, 
            'adoc' as source,
            av.building_id,
            av.level_id,
            av.unit_id,
            pb.building_name,
            bl.level AS level_name,
            bu.unit_no AS unit_name
        FROM adoc_visitor av
        LEFT JOIN property_building pb ON av.building_id = pb.id
        LEFT JOIN building_level bl ON av.level_id = bl.id
        LEFT JOIN building_units bu ON av.unit_id = bu.id
        WHERE av.qr_token = :qr_token
        ORDER BY av.id DESC
        LIMIT 1
    """), {"qr_token": qr_token}).mappings().first()
    
    if not visitor:
        visitor = db.execute(text("""
            SELECT 
                iv.name, 
                iv.phone, 
                iv.purpose_visit, 
                iv.card_no, 
                iv.valid, 
                'invite' as source,
                ua.building_id,
                ua.level_id,
                ua.unit_id,
                pb.building_name,
                bl.level AS level_name,
                bu.unit_no AS unit_name
            FROM invite_visitor iv
            LEFT JOIN user_access_details ua ON iv.user_id = ua.user_id
            LEFT JOIN property_building pb ON ua.building_id = pb.id
            LEFT JOIN building_level bl ON ua.level_id = bl.id
            LEFT JOIN building_units bu ON ua.unit_id = bu.id
            WHERE iv.qr_token = :qr_token
            ORDER BY iv.id DESC
            LIMIT 1
        """), {"qr_token": qr_token}).mappings().first()

    access_level_parts = []
    if visitor and visitor.get("building_name"):
        access_level_parts.append(visitor["building_name"])
    if visitor and visitor.get("level_name"):
        access_level_parts.append(f"Level {visitor['level_name']}")
    if visitor and visitor.get("unit_name"):
        access_level_parts.append(f"Unit {visitor['unit_name']}")
    
    access_level_display = " · ".join(access_level_parts) if access_level_parts else "Main Lobby · General Access"

    context = {
        "request": request,
        "is_valid": False,
        "is_found": bool(visitor),
        "qr_image": None,
        "qr_status": "QR expiry",
        "visitor_name": "",
        "phone": "",
        "purpose_visit": "",
        "valid_until": "N/A",
        "source": visitor.get("source") if visitor else None,
        "access_level": access_level_display,
        "building_name": visitor.get("building_name") if visitor else None,
        "level_name": visitor.get("level_name") if visitor else None,
        "unit_name": visitor.get("unit_name") if visitor else None
    }

    if not visitor:
        context["qr_status"] = "Invalid QR token"
        return templates.TemplateResponse("view_qr_page.html", context)

    valid_data = visitor["valid"]
    if isinstance(valid_data, str):
        try:
            valid_data = json.loads(valid_data)
        except Exception:
            valid_data = {}

    end_time_str = valid_data.get("endTime")
    valid_until = end_time_str or "N/A"
    is_valid = False
    
    if end_time_str:
        try:
            try:
                valid_until_dt = datetime.fromisoformat(end_time_str)
            except:
                valid_until_dt = datetime.strptime(end_time_str, "%Y-%m-%d")
            
            is_valid = datetime.now() <= valid_until_dt
            valid_until = valid_until_dt.strftime("%d %b %Y %I:%M %p")
        except Exception as e:
            print(f"Error parsing date: {e}")
            valid_until = end_time_str

    context.update({
        "visitor_name": visitor.get("name") or "",
        "phone": visitor.get("phone") or "",
        "purpose_visit": visitor.get("purpose_visit") or "",
        "valid_until": valid_until,
        "source": visitor.get("source")
    })

    if is_valid and visitor.get("card_no"):
        qr = qrcode.make(visitor["card_no"])
        buffer = io.BytesIO()
        qr.save(buffer, format="PNG")
        context["qr_image"] = base64.b64encode(buffer.getvalue()).decode("utf-8")
        context["is_valid"] = True
        context["qr_status"] = "Scan to Enter"
    else:
        context["qr_status"] = "QR Expired or Invalid"

    return templates.TemplateResponse("view_qr_page.html", context)
