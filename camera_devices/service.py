from fastapi import APIRouter, Depends, HTTPException,Request
from sqlalchemy import text
from sqlalchemy.orm import Session
from DB.db import SessionLocal
import traceback
from datetime import datetime
from utils.security import encrypt_password, decrypt_password
from utils.security import verify_token
from fastapi import Query
from sqlalchemy.exc import IntegrityError
import socket
import math
import subprocess
import platform

import requests



router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# def check_device_status(ip: str, port: int, timeout: int = 2) -> str:
#     """Check if device is online by trying to connect to IP:Port."""
#     try:
#         with socket.create_connection((ip, port), timeout=timeout):
#             return "online"
#     except (socket.timeout, ConnectionRefusedError, OSError):
#         return "offline"
    


# def quick_ip_check(ip: str, timeout: float = 1.0) -> bool:
#     """Check if IP is reachable on port 443 or 80."""
#     for port in [443, 80]:
#         try:
#             with socket.create_connection((ip, port), timeout=timeout):
#                 return True
#         except Exception:
#             continue
#     return False


# import socket

# def quick_ip_check(ip: str, timeout: float = 1.0) -> bool:
#     """Check if IP is reachable on port 443 or 80."""
#     for port in [443, 80]:
#         try:
#             with socket.create_connection((ip, port), timeout=timeout):
#                 return True
#         except Exception:
#             continue
#     return False


# @router.get("/list_devices_quick")
# async def list_devices_quick(
#     db: Session = Depends(get_db),
#     page: int = Query(1, ge=1, description="Page number (default is 1)"),
#     per_page: int = Query(10, ge=1, le=100, description="Number of items per page (default is 10)")
# ):
#     try:
#         offset = (page - 1) * per_page

#         count_result = db.execute(text("SELECT COUNT(*) FROM camera_devices")).scalar()
#         last_page = math.ceil(count_result / per_page) if count_result else 1

#         query = text("""
#             SELECT d.id, d.name, d.ip, ct.title AS type, d.building_id, d.common_building, 
#                    d.port, d.user_name, d.password, ct.id AS type_id
#             FROM camera_devices d
#             LEFT JOIN camera_type ct ON d.type = ct.id
#             LIMIT :limit OFFSET :offset
#         """)
#         result = db.execute(query, {"limit": per_page, "offset": offset})
#         rows = result.fetchall()

#         if not rows:
#             raise HTTPException(status_code=404, detail="No devices found on this page.")

#         for row in rows:
#             ip = row[2]
#             if not quick_ip_check(ip):
#                 raise HTTPException(
#                     status_code=400,
#                     detail=f"Device with IP '{ip}' is not reachable on port 443 or 80. "
#                            f"Please first go to device management and add the correct device IP."
#                 )

#         return {
#             "status": 200,
#             "message": "All devices are reachable."
#         }

#     except HTTPException as http_exc:
#         raise http_exc
#     except Exception:
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail="Internal Server Error")



def ping_host(ip: str) -> bool:
    """Ping to check if host is reachable (cross-platform)."""
    system = platform.system().lower()
    if system == "windows":
        cmd = ["ping", "-n", "1", "-w", "1000", ip]  
    else:
        cmd = ["ping", "-c", "1", "-W", "1", ip]  

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return result.returncode == 0
    except Exception:
        return False


@router.get("/list_devices")
async def list_devices(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number (default is 1)"),
    per_page: int = Query(10, ge=1, le=100, description="Number of items per page (default is 10)")
):
    try:
        offset = (page - 1) * per_page

        count_result = db.execute(text("SELECT COUNT(*) FROM camera_devices")).scalar()
        last_page = math.ceil(count_result / per_page) if count_result else 1

        query = text("""
            SELECT d.id, d.name, d.ip, ct.title AS type, d.building_id, d.common_building, 
                   d.port, d.user_name, d.password, ct.id AS type_id
            FROM camera_devices d
            LEFT JOIN camera_type ct ON d.type = ct.id
            LIMIT :limit OFFSET :offset
        """)
        result = db.execute(query, {"limit": per_page, "offset": offset})
        rows = result.fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail="No devices found on this page.")

        data = []
        for row in rows:
            ip_address = row[2]
            is_online = ping_host(ip_address)

            print(f"[PING CHECK] Device: {row[1]} ({ip_address}) -> {'ONLINE' if is_online else 'OFFLINE'}")

            device_status = "online" if is_online else "offline"

            data.append({
                "id": row[0],
                "name": row[1],
                "ip": ip_address,
                "type": row[3],
                "building": row[4],
                "common_building": row[5],
                "port": row[6],
                "user_name": row[7],
                "password": row[8],
                "type_id": row[9],
                "status": device_status
            })

        return {
            "status": 200,
            "data": data,
            "pagination_details": {
                "page": page,
                "per_page": per_page,
                "total": count_result,
                "last_page": last_page
            },
            "message": "Devices retrieved successfully."
        }

    except HTTPException as http_exc:
        raise http_exc
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal Server Error")

# @router.get("/get_device/{device_id}", dependencies=[Depends(verify_token)])
# async def get_device(device_id: int, db: Session = Depends(get_db)):
#     try:
#         query = text("""
#             SELECT d.id, d.name, d.ip, ct.title AS type, d.building_id, d.common_building, 
#                    d.port, d.user_name, d.password
#             FROM camera_devices d
#             LEFT JOIN camera_type ct ON d.type = ct.id
#             WHERE d.id = :device_id
#         """)
#         row = db.execute(query, {"device_id": device_id}).fetchone()

#         if not row:
#             raise HTTPException(status_code=404, detail="Device not found.")

#         device_status = check_device_status(row[2], row[6])

#         data = {
#             "id": row[0],
#             "name": row[1],
#             "ip": row[2],
#             "type": row[3],
#             "building": row[4],
#             "common_building": row[5],
#             "port": row[6],
#             "user_name": row[7],
#             "password": row[8],
#             "status": device_status
#         }

#         return {
#             "status": 200,
#             "data": data,
#             "message": "Device retrieved successfully."
#         }

#     except HTTPException:
#         raise
#     except Exception:
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail="Internal Server Error")



    
@router.get("/device_summary")
async def device_summary(db: Session = Depends(get_db)):
    try:
        total_count = db.execute(
            text("SELECT COUNT(*) FROM camera_devices")
        ).scalar()

        fr_count = db.execute(
            text("SELECT COUNT(*) FROM camera_devices WHERE type = '1'")
        ).scalar()

        anpr_count = db.execute(
            text("SELECT COUNT(*) FROM camera_devices WHERE type = '2'")
        ).scalar()

        total_residents = db.execute(
            text("SELECT COUNT(*) FROM user_personal_details")
        ).scalar()

        # Total visitors from invite_visitor table only
        total_invite_visitors = db.execute(
            text("SELECT COUNT(*) FROM invite_visitor")
        ).scalar()

        # Combined visitor count (if you still need both tables combined)
        adoc_visitor_count = db.execute(text("""
            SELECT COUNT(*) FROM (
                SELECT id FROM invite_visitor
                UNION ALL
                SELECT id FROM adoc_visitor
            ) AS combined_visitors
        """)).scalar()

        license_plate_access_count = db.execute(
            text("SELECT COUNT(*) FROM license_plate_access")
        ).scalar()

        return {
            "status": 200,
            "message": "Device summary retrieved successfully.",
            "data": {
                "total_devices": total_count,
                "fr_camera_count": fr_count,
                "anpr_camera_count": anpr_count,
                "total_residents": total_residents,
                "total_visitors": total_invite_visitors,  # Added this field
                "adoc_visitor_count": adoc_visitor_count,  # Kept for backward compatibility
                "license_plate_access_count": license_plate_access_count,
            }
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to get device summary: {str(e)}")







@router.post("/create_devices")
async def create_device(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()

        field_mapping = {
            "Device Name": "name",
            "IP": "ip",
            "User Name": "user_name",
            "Password": "password",
            "Device Type": "type",
            "Device Placement": "building_id"
        }

        for label, key in field_mapping.items():
            if not data.get(key):
                raise HTTPException(status_code=400, detail=f"Field '{label}' is required.")

        encrypted_password = encrypt_password(data["password"])
        is_common = data.get("building_id") == "common"
        port = data.get("port", 443)

        insert_device_query = text("""
            INSERT INTO camera_devices 
            (name, ip, user_name, password, type, port, building_id, common_building, created_date, updated_date)
            VALUES 
            (:name, :ip, :user_name, :password, :type, :port, :building_id, :common_building, :created_date, :updated_date)
        """)

        db.execute(insert_device_query, {
            "name": data["name"],
            "ip": data["ip"],
            "user_name": data.get("user_name"),
            "password": encrypted_password,
            "type": data["type"],
            "port": port, 
            "building_id": None if is_common else data.get("building_id"),
            "common_building": "common" if is_common else None,
            "created_date": datetime.now(),
            "updated_date": datetime.now()
        })

        device_id = db.execute(text("SELECT LAST_INSERT_ID() AS id")).mappings().first()["id"]

        if not is_common:
            assign_query = text("""
                INSERT INTO assign_devices (device_id, building_id, created_at)
                VALUES (:device_id, :building_id, :created_at)
            """)
            db.execute(assign_query, {
                "device_id": device_id,
                "building_id": data["building_id"],
                "created_at": datetime.now()
            })

        db.commit()

        return {
            "status": 201,
            "message": "Device created successfully." if is_common else "Device created and assigned successfully.",
            "data": {
                **data,
                "port": port,
                "device_id": device_id
            },
        }

    except IntegrityError as e:
        db.rollback()
        if "Duplicate entry" in str(e.orig):  
            raise HTTPException(status_code=400, detail="Device with this IP already exists.")
        raise HTTPException(status_code=500, detail="Database error.")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Insert failed: {str(e)}")


@router.put("/update_device/{device_id}", dependencies=[Depends(verify_token)])
async def update_device(device_id: int, request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()

        field_mapping = {
            "Device Name": "name",
            "IP": "ip",
            "User Name": "user_name",
            "Device Type": "type",
            "Device Placement": "building_id"
        }
        for label, key in field_mapping.items():
            if not data.get(key):
                raise HTTPException(status_code=400, detail=f"Field '{label}' is required.")

        encrypted_password = None
        if "password" in data and data["password"]:
            encrypted_password = encrypt_password(data["password"])

        existing_device = db.execute(
            text("SELECT * FROM camera_devices WHERE id = :device_id"),
            {"device_id": device_id}
        ).mappings().first()

        if not existing_device:
            raise HTTPException(status_code=404, detail="Device not found.")

        is_common = data.get("building_id") == "common"
        port = data.get("port", 443)

        update_query = text("""
            UPDATE camera_devices
            SET name = :name,
                ip = :ip,
                user_name = :user_name,
                type = :type,
                port = :port,
                building_id = :building_id,
                common_building = :common_building,
                password = COALESCE(:password, password),
                updated_date = :updated_date
            WHERE id = :device_id
        """)

        db.execute(update_query, {
            "device_id": device_id,
            "name": data["name"],
            "ip": data["ip"],
            "user_name": data.get("user_name"),
            "type": data["type"],
            "port": port,
            "building_id": None if is_common else data.get("building_id"),
            "common_building": "common" if is_common else None,
            "password": encrypted_password,  
            "updated_date": datetime.now()
        })

        if not is_common:
            db.execute(text("DELETE FROM assign_devices WHERE device_id = :device_id"), {"device_id": device_id})
            db.execute(text("""
                INSERT INTO assign_devices (device_id, building_id, created_at)
                VALUES (:device_id, :building_id, :created_at)
            """), {
                "device_id": device_id,
                "building_id": data["building_id"],
                "created_at": datetime.now()
            })
        else:
            db.execute(text("DELETE FROM assign_devices WHERE device_id = :device_id"), {"device_id": device_id})

        db.commit()

        return {
            "status": 200,
            "message": "Device updated successfully.",
            "data": {
                **data,
                "port": port,
                "device_id": device_id
            }
        }

    except IntegrityError as e:
        db.rollback()
        if "Duplicate entry" in str(e.orig):
            raise HTTPException(status_code=400, detail="Device with this IP already exists.")
        raise HTTPException(status_code=500, detail="Database error.")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")




@router.delete("/delete_devices/{device_id}", dependencies=[Depends(verify_token)])
async def delete_device(device_id: int, db: Session = Depends(get_db)):
    try:
        existing_device = db.execute(
            text("SELECT * FROM camera_devices WHERE id = :device_id"),
            {"device_id": device_id}
        ).mappings().first()

        if not existing_device:
            raise HTTPException(status_code=404, detail="Device not found.")

        db.execute(
            text("DELETE FROM assign_devices WHERE device_id = :device_id"),
            {"device_id": device_id}
        )

        db.execute(
            text("DELETE FROM camera_devices WHERE id = :device_id"),
            {"device_id": device_id}
        )

        db.commit()

        return {
            "status": 200,
            "message": f"Device with id {device_id} deleted successfully.",
            "data": {
                "device_id": device_id,
                "name": existing_device["name"],
                "ip": existing_device["ip"],
                "type": existing_device["type"]
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")

