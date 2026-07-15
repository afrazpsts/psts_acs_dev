import requests
import json
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from requests.auth import HTTPDigestAuth
from .models import LicensePlateDeletionRequest
from sqlalchemy.orm import Session
from sqlalchemy import text
from DB.db import get_db
import traceback
from typing import Optional

# DEVICE_IP = "192.168.1.64"
# USERNAME = "admin"
# PASSWORD = "Psts@#12"

def upload_license_plate_info(ip, username, password, plate_info):
    """
    Upload license plate to Hikvision ANPR device
    """
    url = f"http://{ip}/ISAPI/Traffic/channels/1/licensePlateAuditData/record?format=json"
    headers = {"Content-Type": "application/json"}

    # Get current datetime for createTime if not provided
    from datetime import datetime
    current_datetime = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    
    plate_payload = {
        "LicensePlate": plate_info["LicensePlate"],
        "cardID": plate_info.get("cardID", plate_info["cardNo"]),  # Use cardNo as cardID if not provided
        "cardNo": plate_info["cardNo"],
        "certificateNumber": plate_info.get("certificateNumber", ""),
        "certificateType": plate_info.get("certificateType", "ID"),
        "listType": plate_info["listType"],
        "name": plate_info.get("name", ""),
        "operation": plate_info.get("operation", "new"),
        "operationType": plate_info.get("operationType", "add"),
        "plateColor": plate_info.get("plateColor", "blue"),
        "plateDescription": plate_info.get("plateDescription", ""),
        "plateType": plate_info.get("plateType", "92TypeCivil"),
        "virtualParkingNum": plate_info.get("virtualParkingNum", "")
    }

    # Add time fields for allowList (not blockList) - Match dashboard format
    if plate_info["listType"] != "blockList":
        # Format createTime with datetime
        if plate_info.get("createTime"):
            if "T" in plate_info["createTime"]:
                plate_payload["createTime"] = plate_info["createTime"]
            else:
                # Add time component (start of day)
                plate_payload["createTime"] = f"{plate_info['createTime']}T00:00:00"
        else:
            plate_payload["createTime"] = current_datetime
        
        # Format effectiveTime with datetime
        if plate_info.get("effectiveTime"):
            if "T" in plate_info["effectiveTime"]:
                plate_payload["effectiveTime"] = plate_info["effectiveTime"]
            else:
                # Add time component (end of day)
                plate_payload["effectiveTime"] = f"{plate_info['effectiveTime']}T23:59:59"
        else:
            plate_payload["effectiveTime"] = "2099-12-31T23:59:59"
        
        # Add effectiveStartDate (dashboard uses this)
        if plate_info.get("effectiveTime"):
            start_date = plate_info["effectiveTime"].split("T")[0] if "T" in plate_info["effectiveTime"] else plate_info["effectiveTime"]
            plate_payload["effectiveStartDate"] = start_date
        else:
            plate_payload["effectiveStartDate"] = plate_payload["createTime"].split("T")[0]
        
        print(f"  Adding time fields - createTime: {plate_payload['createTime']}, effectiveTime: {plate_payload['effectiveTime']}, effectiveStartDate: {plate_payload['effectiveStartDate']}")

    payload = {"LicensePlateInfoList": [plate_payload]}

    print("Sending Payload:")
    print(json.dumps(payload, indent=4))

    try:
        response = requests.put(
            url,
            auth=requests.auth.HTTPDigestAuth(username, password),
            json=payload,
            headers=headers,
            timeout=15,
            verify=False
        )

        print(f"\nUpload Response: HTTP {response.status_code}")
        print(response.text)

        return response.status_code == 200
    except Exception as e:
        print(f"Error in upload_license_plate_info: {str(e)}")
        return False

def uploading_license_plate_info(device_ip: str, username: str, password: str, plate_info: dict):
    url = f"http://{device_ip}/ISAPI/Traffic/channels/1/licensePlateAuditData/record?format=json"
    headers = {"Content-Type": "application/json"}

    payload = {
        "LicensePlateInfoList": [
            {
                "LicensePlate": plate_info["LicensePlate"],
                "cardID": plate_info.get("cardID", ""),
                "cardNo": plate_info.get("cardNo", ""),
                "certificateNumber": plate_info.get("certificateNumber", ""),
                "certificateType": plate_info.get("certificateType", "ID"),
                "listType": plate_info.get("listType", "allowList"),
                "name": plate_info.get("name", ""),
                "operation": plate_info.get("operation", "new"),
                "operationType": plate_info.get("operationType", "add"),
                "plateColor": plate_info.get("plateColor", "blue"),
                "plateDescription": plate_info.get("plateDescription", ""),
                "plateType": plate_info.get("plateType", "92TypeCivil"),
                "virtualParkingNum": plate_info.get("virtualParkingNum", ""),
                "createtime": plate_info.get("createTime"),
                "effectiveTime": plate_info.get("effectiveTime")
            }
        ]
    }

    response = requests.put(
        url,
        auth=HTTPDigestAuth(username, password),
        json=payload,
        headers=headers,
        timeout=15,
        verify=False
    )

    return response.status_code == 200

def insert_license_plate(db: Session, plate_info: dict):
    """Insert license plate into database"""
    print(f"[LOG] Inserting license plate: {plate_info}")
    
    if plate_info["listType"] == "blockList":
        query = text("""
            INSERT INTO license_plate_access (
                LicensePlate, vehicle_type, iu_number, building_id, resident_id, listType
            ) VALUES (
                :LicensePlate, :vehicle_type, :iu_number, :building_id, :resident_id, :listType
            )
        """)
        params = {
            "building_id": plate_info["building_id"],
            "resident_id": plate_info["resident_id"],
            "LicensePlate": plate_info["LicensePlate"],
            "vehicle_type": plate_info["vehicle_type"],
            "iu_number": plate_info["iu_number"],
            "listType": plate_info["listType"]
        }
    else:
        query = text("""
            INSERT INTO license_plate_access (
                LicensePlate, vehicle_type, iu_number, building_id, resident_id, listType, 
                createTime, effectiveTime
            ) VALUES (
                :LicensePlate, :vehicle_type, :iu_number, :building_id, :resident_id, :listType, 
                :createTime, :effectiveTime
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
            "effectiveTime": plate_info["effectiveTime"]
        }
    
    try:
        db.execute(query, params)
        db.commit()
        print(f" License plate {plate_info['LicensePlate']} inserted successfully")
        return {"message": "License plate inserted successfully"}
    except IntegrityError as e:
        db.rollback()
        error_message = str(e.orig).lower()
        if "uq_card_no" in error_message or "iu_number" in error_message:
            raise HTTPException(
                status_code=400,
                detail=f"IU Number '{plate_info['iu_number']}' already exists."
            )
        elif "uq_license_plate" in error_message or "licenseplate" in error_message:
            raise HTTPException(
                status_code=400,
                detail=f"License plate '{plate_info['LicensePlate']}' already exists."
            )
        else:
            raise HTTPException(status_code=400, detail=f"Duplicate entry: {error_message}")
# def insert_license_plate(db: Session, plate_info: dict):
#     """
#     Insert a license plate into license_plate_access.
#     Enforces uniqueness on cardNo and LicensePlate.
#     """

#     print("\n[LOG] insert_license_plate called with plate_info:", plate_info)

#     if plate_info["listType"] == "blockList":
#         query = text("""
#             INSERT INTO license_plate_access (
#                 LicensePlate,vehicle_type, cardNo, building_id, resident_id, listType
#             ) VALUES (
#                 :LicensePlate, :vehicle_type, :cardNo, :building_id, :resident_id, :listType
#             )
#         """)
#         params = {
#             "building_id": plate_info["building_id"],
#             "resident_id": plate_info["resident_id"],
#             "LicensePlate": plate_info["LicensePlate"],
#             "vehicle_type": plate_info["vehicle_type"],
#             "cardNo": plate_info["cardNo"],
#             "listType": plate_info["listType"]
#         }
#     else:
#         query = text("""
#             INSERT INTO license_plate_access (
#                 LicensePlate, vehicle_type, cardNo, building_id, resident_id, listType, createTime, effectiveTime
#             ) VALUES (
#                 :LicensePlate, :vehicle_type, :cardNo, :building_id, :resident_id, :listType, :createTime, :effectiveTime
#             )
#         """)
#         params = {
#             "building_id": plate_info["building_id"],
#             "resident_id": plate_info["resident_id"],
#             "LicensePlate": plate_info["LicensePlate"],
#             "vehicle_type": plate_info["vehicle_type"],
#             "cardNo": plate_info["cardNo"],
#             "listType": plate_info["listType"],
#             "createTime": plate_info["createTime"],
#             "effectiveTime": plate_info["effectiveTime"]
#         }

#     print("[LOG] Executing DB Insert with params:", params)

#     try:
#         db.execute(query, params)
#         db.commit()
#         print("[LOG] License plate inserted successfully in DB")
#         return {"message": "License plate inserted successfully"}

#     except IntegrityError as e:
#         db.rollback()
#         error_message = str(e.orig).lower()
#         print("[ERROR] IntegrityError occurred:", error_message)

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
#             raise HTTPException(
#                 status_code=400,
#                 detail=f"Duplicate entry detected: {error_message}"
#             )

#     except Exception as e:
#         db.rollback()
#         print("[ERROR] Unexpected error in insert_license_plate:", str(e))
#         raise HTTPException(
#             status_code=500,
#             detail=f"An unexpected error occurred: {str(e)}"
#         )
    


def delete_license_plate_from_db(db: Session, license_plate: str):
    try:
        query = text("""
            DELETE FROM license_plate_access
            WHERE LicensePlate = :LicensePlate
        """)
        params = {"LicensePlate": license_plate}
        result = db.execute(query, params)
        db.commit()

        if result.rowcount == 0:
            return None  

        return {"message": f"License plate {license_plate} deleted from database."}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


def delete_license_plate_from_device(license_plate: str, device_ip: str, username: str, password: str):
    url = f"http://{device_ip}/ISAPI/Traffic/channels/1/DelLicensePlateAuditData?format=json"
    payload = {
        "deleteAllEnabled": False,
        "CompoundCond": {
            "plateColor": "",
            "licensePlate": license_plate
        }
    }

    response = requests.put(
        url,
        auth=HTTPDigestAuth(username, password),
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=15,
        verify=False
    )

    if response.status_code == 200:
        return {"message": "Deleted successfully", "device_response": response.json()}
    else:
        raise HTTPException(status_code=response.status_code, detail=f"Device deletion failed: {response.text}")
    
# def delete_license_plate_info_from_device(payload_dict: dict,username,password,DEVICE_IP):
#     url = f"http://{DEVICE_IP}/ISAPI/Traffic/channels/1/DelLicensePlateAuditData?format=json"
    
#     print("Sending Payload for Deletion:")
#     print(json.dumps(payload_dict, indent=4))

#     try:
#         response = requests.put(
#             url,
#             auth=HTTPDigestAuth(username, password),
#             json=payload_dict,
#             headers={"Content-Type": "application/json"},
#             timeout=15,
#             verify=False  
#         )

#         if response.status_code == 200:
#             return {"message": "License plate data deleted successfully."}
#         else:
#             raise HTTPException(status_code=response.status_code, detail=f"Deletion failed. Response: {response.text}")
    
#     except requests.RequestException as e:
#         raise HTTPException(status_code=500, detail=f"Request failed: {str(e)}")
    


def get_license_plate_access_records(
    db: Session,
    resident_id: Optional[int] = None,
    vehicle_owner: Optional[str] = None,
    page: int = 1,
    per_page: int = 10,
    search: Optional[str] = None,
    sort: Optional[str] = None,
    use_pagination: bool = True
):
    try:
        offset = (page - 1) * per_page if use_pagination else 0

        filters = []
        params = {}
        
        if resident_id is not None:
            filters.append("lpa.resident_id = :resident_id")
            params["resident_id"] = resident_id
        
        if vehicle_owner is not None:
            filters.append("lpa.source = :vehicle_owner")
            params["vehicle_owner"] = vehicle_owner
        
        if search:
            filters.append("""(
                lpa.LicensePlate LIKE :search OR 
                lpa.iu_number LIKE :search OR 
                upd.first_name LIKE :search OR 
                upd.last_name LIKE :search
            )""")
            params["search"] = f"%{search}%"

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

        if sort == "old":
            order_clause = "ORDER BY lpa.id ASC"
        else:
            order_clause = "ORDER BY lpa.id DESC"

        limit_clause = ""
        if use_pagination:
            limit_clause = "LIMIT :limit OFFSET :offset"
            params["limit"] = per_page
            params["offset"] = offset

        query = text(f"""
            SELECT 
                lpa.id,
                lpa.building_id,
                lpa.LicensePlate,
                lpa.iu_number,
                lpa.listType,
                lpa.createTime,
                lpa.effectiveTime,
                pb.building_name,
                lpa.resident_id,
                upd.first_name,
                upd.last_name,
                upd.email,
                upd.phone,
                lpa.vehicle_type,
                vt.title AS vehicle_type_title,
                lpa.source AS vehicle_owner_type
            FROM license_plate_access lpa
            LEFT JOIN property_building pb ON lpa.building_id = pb.id
            LEFT JOIN user_personal_details upd ON lpa.resident_id = upd.id
            LEFT JOIN vehicle_type vt ON lpa.vehicle_type = vt.id
            {where_clause}
            {order_clause}
            {limit_clause}
        """)
        
        rows = db.execute(query, params).fetchall()

        count_query = text(f"""
            SELECT COUNT(*) 
            FROM license_plate_access lpa
            LEFT JOIN user_personal_details upd ON lpa.resident_id = upd.id
            {where_clause}
        """)
        total_count = db.execute(count_query, params).scalar() or 0

        data = []
        for row in rows:
            data.append({
                "id": row[0],
                "building_id": row[1],
                "license_plate": row[2],
                "iu_number": row[3],
                "list_type": row[4],
                "create_time": row[5],
                "effective_time": row[6],
                "building_name": row[7],
                "resident_id": row[8],
                "resident_first_name": row[9],
                "resident_last_name": row[10],
                "resident_email": row[11],
                "resident_phone": row[12],
                "vehicle_type_id": row[13],
                "vehicle_type": row[14],
                "vehicle_owner_type": row[15]  
            })

        return data, total_count
        
    except Exception as e:
        traceback.print_exc()
        raise Exception(f"Error in get_license_plate_access_records: {str(e)}")