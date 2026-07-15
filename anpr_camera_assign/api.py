from fastapi import APIRouter,Depends,HTTPException, Request
from typing import Optional
from .service import upload_license_plate_info, insert_license_plate, delete_license_plate_from_db,get_license_plate_access_records,delete_license_plate_from_device,uploading_license_plate_info
from DB.db import get_db
from sqlalchemy.orm import Session
import traceback
from utils.security import verify_token 
from sqlalchemy import text
from fastapi import Query
from.models import LicensePlateRequest,LicensePlateDeletionRequest,AddPlateRequest,UpdatePlatePayload
import requests
from requests.auth import HTTPDigestAuth
from utils.security import decrypt_password


router = APIRouter()

# DEVICE_IP = "192.168.1.64"
# USERNAME = "admin"
# PASSWORD = "Psts@#12"

@router.post("/add_license_plate")
def add_license_plate(data: AddPlateRequest, db: Session = Depends(get_db)):
    print("\n[LOG] add_license_plate called with data:", data.dict())

    existing_plate = db.execute(
        text("""
            SELECT id 
            FROM license_plate_access
            WHERE LicensePlate = :LicensePlate
            AND building_id = :building_id
            AND listType = :listType
            LIMIT 1
        """),
        {
            "LicensePlate": data.LicensePlate,
            "building_id": data.building_id,
            "listType": data.listType
        }
    ).fetchone()

    print("[LOG] Existing plate check result:", existing_plate)

    if existing_plate:
        raise HTTPException(
            status_code=400,
            detail=f"License plate '{data.LicensePlate}' already exists."
        )

    validity_query = text("""
        SELECT JSON_UNQUOTE(JSON_EXTRACT(valid, '$.beginTime')) AS beginTime,
               JSON_UNQUOTE(JSON_EXTRACT(valid, '$.endTime')) AS endTime
        FROM resident_device_assign
        WHERE user_id = :resident_id
        LIMIT 1
    """)
    validity = db.execute(validity_query, {"resident_id": data.resident_id}).fetchone()

    print("[LOG] Validity check result:", validity)

    begin_time = validity.beginTime if validity else None
    end_time = validity.endTime if validity else None

    plate_info = {
        "LicensePlate": data.LicensePlate,
        "cardID": "",
        "cardNo": data.cardNo,
        "certificateNumber": "",
        "certificateType": "ID",
        "building_id": data.building_id,
        "resident_id": data.resident_id,
        "vehicle_type": "car",
        "listType": data.listType,
        "name": "",
        "operation": "new",
        "operationType": "add",
        "plateColor": "blue",
        "plateDescription": "",
        "plateType": "92TypeCivil",
        "virtualParkingNum": "",
        "createTime": begin_time if data.listType != "blockList" else None,
        "effectiveTime": end_time if data.listType != "blockList" else None
    }

    print("[LOG] Prepared plate_info payload:", plate_info)

    try:
        insert_license_plate(db, plate_info)
    except HTTPException as e:
        print("[ERROR] insert_license_plate failed:", str(e.detail))
        raise e

    building_devices = db.execute(text("""
        SELECT ip, user_name, password
        FROM camera_devices
        WHERE building_id = :building_id AND type = 2
    """), {"building_id": data.building_id}).fetchall()

    common_devices = db.execute(text("""
        SELECT ip, user_name, password
        FROM camera_devices
        WHERE common_building = 'common' AND type = 2
    """)).fetchall()

    devices = {d[0]: d for d in building_devices + common_devices}
    devices = list(devices.values())

    print("[LOG] Retrieved devices:", devices)

    if not devices:
        db.execute(
            text("DELETE FROM license_plate_access WHERE LicensePlate = :plate AND building_id = :bid"),
            {"plate": data.LicensePlate, "bid": data.building_id}
        )
        db.commit()
        print("[ERROR] No ANPR devices found, rolled back plate insert")
        raise HTTPException(
            status_code=404,
            detail="ANPR camera device not available for this building or common setup"
        )

    uploaded_devices = []
    failed_devices = []

    for device in devices:
        device_ip, username, encrypted_password = device
        print(f"[LOG] Uploading plate to device {device_ip} with user {username}")
        try:
            password = decrypt_password(encrypted_password)
            success = upload_license_plate_info(device_ip, username, password, plate_info)
            print(f"[LOG] Upload result for {device_ip}: {success}")
            if success:
                uploaded_devices.append(device_ip)
            else:
                failed_devices.append(device_ip)
        except Exception as e:
            print(f"[ERROR] Exception uploading to {device_ip}:", str(e))
            failed_devices.append(device_ip)

    if not uploaded_devices:
        db.execute(
            text("DELETE FROM license_plate_access WHERE LicensePlate = :plate AND building_id = :bid"),
            {"plate": data.LicensePlate, "bid": data.building_id}
        )
        db.commit()
        print("[ERROR] Upload failed on all devices, rolled back plate insert")
        raise HTTPException(status_code=500, detail="Failed to upload license plate to any device")

    print("[LOG] Final result - uploaded:", uploaded_devices, "failed:", failed_devices)

    return {
        "status": 201,
        "message": "Vehicle added successfully",
        "uploaded_to_devices": uploaded_devices,
        "failed_devices": failed_devices,
        "device_count": len(uploaded_devices),
        "validity": {
            "beginTime": begin_time,
            "endTime": end_time
        } if data.listType != "blockList" else {}
    }


@router.put("/update_license_plate")
def update_license_plate(
    id: int = Query(..., description="License plate record ID"),
    payload: UpdatePlatePayload = None,
    db: Session = Depends(get_db)
):
    try:
        old_record = db.execute(
            text("""
                SELECT LicensePlate, cardNo, building_id, resident_id, listType
                FROM license_plate_access
                WHERE id = :id
            """),
            {"id": id}
        ).fetchone()

        if not old_record:
            raise HTTPException(status_code=404, detail="License plate record not found.")

        old_plate = old_record.LicensePlate
        building_id = old_record.building_id
        resident_id = old_record.resident_id
        old_listType = old_record.listType
        old_cardNo = old_record.cardNo

        building_devices = db.execute(
            text("SELECT ip, user_name, password FROM camera_devices WHERE building_id = :building_id AND type = 2"),
            {"building_id": building_id}
        ).fetchall()

        common_devices = db.execute(
            text("SELECT ip, user_name, password FROM camera_devices WHERE common_building = 'common' AND type = 2")
        ).fetchall()

        devices = {d[0]: d for d in building_devices + common_devices}  # avoid duplicates
        devices = list(devices.values())

        if not devices:
            raise HTTPException(status_code=404, detail="No ANPR devices found for this building/common setup.")

        failed_delete = []
        for device in devices:
            device_ip, username, encrypted_password = device
            try:
                password = decrypt_password(encrypted_password)
                delete_license_plate_from_device(old_plate, device_ip, username, password)
            except Exception:
                failed_delete.append(device_ip)

        if failed_delete:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete old plate from devices: {failed_delete}"
            )

        new_plate = payload.new_license_plate
        cardNo = payload.cardNo or old_cardNo
        listType = payload.listType or old_listType

        if listType != "blockList":
            validity = db.execute(
                text("""
                    SELECT JSON_UNQUOTE(JSON_EXTRACT(valid, '$.beginTime')) AS beginTime,
                           JSON_UNQUOTE(JSON_EXTRACT(valid, '$.endTime')) AS endTime
                    FROM resident_device_assign
                    WHERE user_id = :resident_id
                    LIMIT 1
                """),
                {"resident_id": resident_id}
            ).fetchone()
            begin_time = validity.beginTime if validity else None
            end_time = validity.endTime if validity else None
        else:
            begin_time = None
            end_time = None

        db.execute(
            text("""
                UPDATE license_plate_access
                SET LicensePlate = :new_plate,
                    cardNo = :cardNo,
                    listType = :listType,
                    createTime = :createTime,
                    effectiveTime = :effectiveTime
                WHERE id = :id
            """),
            {
                "new_plate": new_plate,
                "cardNo": cardNo,
                "listType": listType,
                "createTime": begin_time,
                "effectiveTime": end_time,
                "id": id
            }
        )
        db.commit()

        plate_info = {
            "LicensePlate": new_plate,
            "cardID": "",
            "cardNo": cardNo,
            "certificateNumber": "",
            "certificateType": "ID",
            "building_id": building_id,
            "resident_id": resident_id,
            "listType": listType,
            "name": "",
            "operation": "new",
            "operationType": "add",
            "plateColor": "blue",
            "plateDescription": "",
            "plateType": "92TypeCivil",
            "virtualParkingNum": "",
            "createTime": begin_time,
            "effectiveTime": end_time
        }

        uploaded_devices = []
        failed_devices = []

        for device in devices:
            device_ip, username, encrypted_password = device
            try:
                password = decrypt_password(encrypted_password)
                success = upload_license_plate_info(device_ip, username, password, plate_info)
                if success:
                    uploaded_devices.append(device_ip)
                else:
                    failed_devices.append(device_ip)
            except Exception:
                failed_devices.append(device_ip)

        return {
            "status": 200,
            "message": f"License plate updated from {old_plate} to {new_plate}",
            "uploaded_to_devices": uploaded_devices,
            "failed_devices": failed_devices
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")





@router.delete("/delete_license_plate")
def delete_license_plate(id: int = Query(..., description="License plate record ID"), db: Session = Depends(get_db)):
    try:
        plate_info = db.execute(
            text("SELECT LicensePlate, building_id FROM license_plate_access WHERE id = :id"),
            {"id": id}
        ).fetchone()

        if not plate_info:
            raise HTTPException(status_code=404, detail="License plate ID not found in database.")

        license_plate = plate_info.LicensePlate
        building_id = plate_info.building_id

        devices = db.execute(
            text("""
                SELECT ip, user_name, password
                FROM camera_devices
                WHERE type = 2 AND (building_id = :building_id OR common_building = 'common')
            """),
            {"building_id": building_id}
        ).fetchall()

        if not devices:
            raise HTTPException(status_code=404, detail="No ANPR devices found for this building or common setup.")

        uploaded_devices = []
        failed_devices = []

        for device in devices:
            device_ip, username, encrypted_password = device
            try:
                password = decrypt_password(encrypted_password)
                resp = delete_license_plate_from_device(license_plate, device_ip, username, password)
                uploaded_devices.append({"device_ip": device_ip, "response": resp})
            except Exception:
                failed_devices.append(device_ip)

        db.execute(text("DELETE FROM license_plate_access WHERE id = :id"), {"id": id})
        db.commit()

        return {
            "status": 200,
            "message": f" Vehicle has been deleted successfully.",
            "deleted_from_db": True,
            "deleted_from_devices": uploaded_devices,
            "failed_devices": failed_devices
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


    
# @router.put("/delete_license_plate_bulk")
# async def delete_license_plate_info(payload: LicensePlateDeletionRequest):
#     payload_dict = payload.dict()

#     try:
#         result = delete_license_plate_info_from_device(payload_dict)
#         return result
#     except HTTPException as e:
#         raise HTTPException(status_code=e.status_code, detail=e.detail)
    
@router.get("/list_license_plate_access")
def list_license_plate_access(
    resident_id: Optional[int] = Query(None, description="Filter by specific resident ID"),
    vehicle_owner: Optional[str] = Query(None, description="Filter by vehicle owner type: 'resident' or 'visitor'"),
    page: Optional[int] = Query(1, ge=1, description="Page number (ignored if resident_id is provided)"),
    per_page: Optional[int] = Query(10, ge=1, le=100, description="Items per page (ignored if resident_id is provided)"),
    search: Optional[str] = Query(None, description="Search by license plate, card number, or resident name"),
    sort: Optional[str] = Query(None, regex="^(recent|old|null)$"),
    db: Session = Depends(get_db)
):
    try:
        if vehicle_owner and vehicle_owner.lower() not in ['resident', 'visitor']:
            raise HTTPException(status_code=400, detail="vehicle_owner must be 'resident' or 'visitor'")
        
        use_pagination = resident_id is None
        
        data, total_count = get_license_plate_access_records(
            db=db,
            resident_id=resident_id,
            vehicle_owner=vehicle_owner.lower() if vehicle_owner else None,
            page=page if use_pagination else 1,
            per_page=per_page if use_pagination else 999999,
            search=search,
            sort=sort,
            use_pagination=use_pagination
        )

        last_page = (total_count + per_page - 1) // per_page if total_count and use_pagination else 1

        return {
            "status": 200,
            "message": "License plate access records retrieved successfully.",
            "data": data,
            "pagination_details": {
                "page": page if use_pagination else 1,
                "per_page": per_page if use_pagination else total_count,
                "total": total_count,
                "last_page": last_page,
                "pagination_enabled": use_pagination
            },
            "filter_info": {
                "resident_id": resident_id,
                "vehicle_owner": vehicle_owner,
                "search": search,
                "sort": sort
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal Server Error")

