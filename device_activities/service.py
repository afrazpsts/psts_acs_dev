from datetime import datetime, timedelta
import json
from fastapi import APIRouter, Depends, HTTPException,Request,Query,UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import text
from requests.auth import HTTPDigestAuth
from .models import EventQuery
from utils.security import verify_token
from DB.db import get_db

import requests
from sqlalchemy import text
from device_activities.device_activities import DeviceActivities
from notificationss.firebase_service import send_push_notification,send_push_notification_with_preference 
import traceback
from typing import Optional
import xml.etree.ElementTree as ET
from common.logger import log as write_to_server_log
from activity_logs.service import log_activity

router = APIRouter()

# EVENT_CODES = {
#     (5, 2): "Invalid time period",
#     (5, 3): "Anti-passback",
#     (5, 4): "Interlock",
#     (5, 5): "Duress alarm",
#     (5, 6): "Open door failed",
#     (5, 7): "Door opened",
#     (5, 8): "Permission Expired",
#     (5, 9): "No Card No.Found",
#     (5, 10): "Face authentication failed",
#     (5, 11): "Card and face mismatch",
#     (5, 15): "Permission expired",
#     (5, 28): "Door Open Timed Out (Door Contact)",
#     (5, 75): "QR code authentication failed",
#     (5, 76): "Authentication via Face Failed",  
#     (5, 77): "QR code usage exceeded",
#     (5, 78): "QR code not in valid time range",
#     (5, 79): "QR code doesn't exist",
#     (5, 80): "Face not found in face group",
#     (5, 81): "Card not found in card group",
#     (2, 1024): "Device Powering On",
#     (5, 27): "Device Abnormally Open (Door Contact)",
#     (5, 21): "Door Unlocked",
#     (5, 22): "Door Locked",
#     (5, 1): "Legal Card Authenticated",
#     (3, 112): "Remote:Login",
#     (3, 122): "Remote:Alarm Disarming",
#     (3, 121): "Remote:Alarm Arming",
#     (1, 1028): "Device Tampered",
# }



    
@router.get("/get_resident_events")
def get_resident_events(
    user_id: Optional[int] = Query(None, description="Filter events by user_id from resident_device_assign"),
    search: Optional[str] = Query(None, description="Optional search string to filter by name or employeeNoString"),
    query: Optional[dict] = None,
    db: Session = Depends(get_db)
):
    if user_id:
        employee_nos = db.execute(text("""
            SELECT employee_no 
            FROM resident_device_assign 
            WHERE user_id = :user_id
        """), {"user_id": user_id}).scalars().all()

        if not employee_nos:
            raise HTTPException(status_code=404, detail="No employee_no found for this user_id")

        sql = """
            SELECT id, device_activities, created_at
            FROM device_activities
            WHERE JSON_UNQUOTE(JSON_EXTRACT(device_activities, '$.employeeNoString')) IN :employee_nos
        """

        if search:
            sql += """
                AND (
                    LOWER(JSON_UNQUOTE(JSON_EXTRACT(device_activities, '$.name'))) LIKE LOWER(:search)
                    OR LOWER(JSON_UNQUOTE(JSON_EXTRACT(device_activities, '$.employeeNoString'))) LIKE LOWER(:search)
                )
            """

        sql += " ORDER BY created_at DESC"

        params = {"employee_nos": tuple(employee_nos)}
        if search:
            params["search"] = f"%{search}%"

        results = db.execute(text(sql), params).mappings().all()

        events = []
        for row in results:
            try:
                data = json.loads(row["device_activities"])
            except Exception:
                data = {}

            major = data.get("majorEventType")
            minor = data.get("subEventType")
            event_type = EVENT_CODES.get((major, minor), f"Unknown ({major}, {minor})")

            events.append({
                "id": row["id"],
                "created_at": row["created_at"],
                "event": data,
                "event_type": event_type
            })

        return {
            "success": True,
            "source": "device_activities",
            "total_events": len(events),
            "events": events
        }

    if not query:
        raise HTTPException(status_code=400, detail="Either user_id (query param) or device_id (in body) is required")

    device_id = query.get("device_id")
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required in request body if user_id not provided")

    result = db.execute(
        text("SELECT ip, user_name, password FROM camera_devices WHERE id = :device_id"),
        {"device_id": device_id}
    ).mappings().first()

    if not result:
        raise HTTPException(status_code=404, detail="Device not found.")

    device_ip = result["ip"]
    username = result["user_name"]
    password = result["password"]

    url = f"http://{device_ip}/ISAPI/AccessControl/AcsEvent?format=json"

    payload = {
        "AcsEventCond": {
            "searchID": "test",
            "searchResultPosition": 0,
            "maxResults": query.get("maxResults", 50),
            "major": 0,
            "minor": 0,
            "startTime": query.get("startTime"),
            "endTime": query.get("endTime"),
            "timeReverseOrder": True
        }
    }

    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(
            url,
            data=json.dumps(payload),
            headers=headers,
            auth=HTTPDigestAuth(username, password),
            verify=False,
            timeout=15
        )

        if response.status_code == 200:
            data = response.json()
            events = data.get("AcsEvent", {}).get("InfoList", [])

            if search:
                search_lower = search.lower()
                events = [
                    e for e in events
                    if search_lower in e.get("name", "").lower()
                    or search_lower in e.get("employeeNoString", "").lower()
                ]

            for event in events:
                major = event.get("major")
                minor = event.get("minor")
                event["event_type"] = EVENT_CODES.get((major, minor), f"Unknown ({major}, {minor})")

            return {
                "success": True,
                "source": "hikvision_device",
                "total_events": len(events),
                "events": events
            }

        raise HTTPException(status_code=response.status_code, detail=response.text)

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error contacting device: {str(e)}")



@router.get("/get_visitor_events")
def get_visitor_events(
    user_id: Optional[int] = Query(None, description="Filter events by user_id from  invite_visitor"),
    search: Optional[str] = Query(None, description="Optional search string to filter by name or employeeNoString"),
    query: Optional[dict] = None,
    db: Session = Depends(get_db)
):
    if user_id:
        visitor_ids = db.execute(
            text("SELECT visitor_id FROM  invite_visitor WHERE user_id = :user_id"),
            {"user_id": user_id}
        ).scalars().all()

        if not visitor_ids:
            raise HTTPException(status_code=404, detail="No visitors found for this user_id")

        sql = """
            SELECT id, device_activities, created_at
            FROM device_activities
            WHERE JSON_UNQUOTE(JSON_EXTRACT(device_activities, '$.employeeNoString')) IN :visitor_ids
        """

        if search:
            sql += " AND JSON_UNQUOTE(JSON_EXTRACT(device_activities, '$.name')) LIKE :search"

        sql += " ORDER BY created_at DESC"

        params = {"visitor_ids": tuple(visitor_ids)}
        if search:
            params["search"] = f"%{search}%"

        results = db.execute(text(sql), params).mappings().all()

        events = []
        for row in results:
            try:
                data = json.loads(row["device_activities"])
            except Exception:
                data = {}

            major = data.get("majorEventType")
            minor = data.get("subEventType")
            event_type = EVENT_CODES.get((major, minor), f"Unknown ({major}, {minor})")

            events.append({
                "id": row["id"],
                "created_at": row["created_at"],
                "event": data,
                "event_type": event_type
            })

        return {
            "success": True,
            "source": "device_activities",
            "total_events": len(events),
            "events": events
        }

    if not query:
        raise HTTPException(status_code=400, detail="Either user_id (query param) or device_id (in body) is required")

    device_id = query.get("device_id")
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required in request body if user_id not provided")

    result = db.execute(
        text("SELECT ip, user_name, password FROM camera_devices WHERE id = :device_id"),
        {"device_id": device_id}
    ).mappings().first()

    if not result:
        raise HTTPException(status_code=404, detail="Device not found.")

    device_ip = result["ip"]
    username = result["user_name"]
    password = result["password"]

    url = f"http://{device_ip}/ISAPI/AccessControl/AcsEvent?format=json"

    payload = {
        "AcsEventCond": {
            "searchID": "test",
            "searchResultPosition": 0,
            "maxResults": query.get("maxResults", 50),
            "major": 0,
            "minor": 0,
            "startTime": query.get("startTime"),
            "endTime": query.get("endTime"),
            "timeReverseOrder": True
        }
    }

    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(
            url,
            data=json.dumps(payload),
            headers=headers,
            auth=HTTPDigestAuth(username, password),
            verify=False,
            timeout=15
        )

        if response.status_code == 200:
            data = response.json()
            events = data.get("AcsEvent", {}).get("InfoList", [])

            if search:
                events = [e for e in events if search.lower() in e.get("name", "").lower()]

            for event in events:
                major = event.get("major")
                minor = event.get("minor")
                event["event_type"] = EVENT_CODES.get((major, minor), f"Unknown ({major}, {minor})")

            return {
                "success": True,
                "source": "hikvision_device",
                "total_events": len(events),
                "events": events
            }

        raise HTTPException(status_code=response.status_code, detail=response.text)

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error contacting device: {str(e)}")
    
    
@router.post("/get_events", dependencies=[Depends(verify_token)])
def get_events(query: EventQuery, db: Session = Depends(get_db)):

    result = db.execute(
        text("""
            SELECT ip, user_name, password
            FROM camera_devices
            WHERE id = :device_id
        """), {"device_id": query.device_id}
    ).mappings().first()

    if not result:
        raise HTTPException(status_code=404, detail="Device not found.")

    device_ip = result["ip"]
    username = result["user_name"]
    password = result["password"]

    url = f"http://{device_ip}/ISAPI/AccessControl/AcsEvent?format=json"

    payload = {
        "AcsEventCond": {
            "searchID": "test",
            "searchResultPosition": 0,
            "maxResults": query.maxResults,
            "major": 0,
            "minor": 0,
            "startTime": query.startTime,
            "endTime": query.endTime,
            "timeReverseOrder": True
        }
    }

    headers = {
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            url,
            data=json.dumps(payload),
            headers=headers,
            auth=HTTPDigestAuth(username, password),
            verify=False,
            timeout=15
        )

        if response.status_code == 200:
            data = response.json()
            events = data.get("AcsEvent", {}).get("InfoList", [])
            for event in events:
                major = event.get("major")
                minor = event.get("minor")
                event["event_type"] = EVENT_CODES.get((major, minor), f"Unknown ({major}, {minor})")

            return {
                "success": True,
                "total_events": len(events),
                "events": events
            }

        raise HTTPException(status_code=response.status_code, detail=response.text)

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))
    

    
# @router.post("/hikvision-webhook")
# async def hikvision_event(request: Request):
#     data = await request.body()
#     print("Received:", data)
#     return {"status": "received","data":data}


@router.post("/hikvision-webhook")
async def hikvision_event(request: Request, db: Session = Depends(get_db)):
    try:
        form = await request.form()
        print("==== Incoming Hikvision Webhook ====")
        print("Raw Form Data:", dict(form))
        event_log_raw = form.get("event_log")

        if not event_log_raw:
            print("No event_log found in incoming request.")
            return {"status": "no event_log field found"}

        try:
            event_data = json.loads(event_log_raw)
        except json.JSONDecodeError as e:
            print("JSON decode failed:", e)
            return {"status": "invalid JSON"}

        access_event = event_data.get("AccessControllerEvent", {})
        filtered_event = {
            "deviceName": access_event.get("deviceName"),
            "majorEventType": access_event.get("majorEventType"),
            "subEventType": access_event.get("subEventType"),
            "cardNo": access_event.get("cardNo"),
            "cardType": access_event.get("cardType"),
            "name": access_event.get("name"),
            "cardReaderKind": access_event.get("cardReaderKind"),
            "employeeNoString": access_event.get("employeeNoString"),
            "userType": access_event.get("userType"),
            "dateTime": event_data.get("dateTime"),
        }

        print("Filtered event data:", filtered_event)

        major = access_event.get("majorEventType")
        sub = access_event.get("subEventType")

        if major == 5 and sub == 8:
            print("User Permission Expired event received. Skipping notification.")
            return {"status": "skipped_permission_expired"}

        activity_id = None
        if major == 5 and sub in [38, 75, 1]:
            activity = DeviceActivities(device_activities=filtered_event)
            db.add(activity)
            db.commit()
            db.refresh(activity)
            activity_id = activity.id
            print("Stored event ID:", activity.id)

        user_type = access_event.get("userType")
        employee_no = access_event.get("employeeNoString")

        if (
            access_event.get("cardReaderKind") == 1
            and major == 5
            and user_type == "visitor"
            and employee_no
        ):
            print(f"Visitor detected with employeeNoString={employee_no}")

            visitor_record = db.execute(
                text("""
                    SELECT v.visitor_id, v.user_id, v.name AS visitor_name, u.fcm_token
                    FROM  invite_visitor v
                    JOIN user_personal_details u ON v.user_id = u.id
                    WHERE v.visitor_id = :emp_no
                """),
                {"emp_no": employee_no}
            ).mappings().fetchone()

            if visitor_record:
                fcm_token = visitor_record.get("fcm_token")
                if fcm_token:
                    visitor_name = visitor_record.get("visitor_name", "Visitor")
                    notif = send_push_notification_with_preference(
                        db=db,
                        user_id=visitor_record["user_id"], 
                        title="New visitor arrived",
                        body=f"{visitor_name} has entered successfully",
                        notification_type="activities",
                    )
                    print("Notification result:", notif)
                else:
                    print(f"No FCM token for user_id={visitor_record['user_id']}")
            else:
                print(f"No visitor mapping found in  invite_visitor for {employee_no}")

            adoc_visitor_record = db.execute(
                text("""
                    SELECT av.adoc_visitor_id, av.building_id, av.level_id, av.unit_id, av.name AS visitor_name
                    FROM adoc_visitor av
                    WHERE av.adoc_visitor_id = :emp_no
                """),
                {"emp_no": employee_no}
            ).mappings().fetchone()

            if adoc_visitor_record:
                print(f"Found in adoc_visitor: {adoc_visitor_record}")

                resident = db.execute(
                    text("""
                        SELECT uad.user_id, upd.fcm_token
                        FROM user_access_details uad
                        JOIN user_personal_details upd ON uad.user_id = upd.id
                        WHERE uad.building_id = :building_id
                          AND uad.level_id = :level_id
                          AND uad.unit_id = :unit_id
                    """),
                    {
                        "building_id": adoc_visitor_record["building_id"],
                        "level_id": adoc_visitor_record["level_id"],
                        "unit_id": adoc_visitor_record["unit_id"],
                    }
                ).mappings().fetchone()

                if resident and resident.get("fcm_token"):
                    visitor_name = adoc_visitor_record.get("visitor_name", "Visitor")
                    notif = send_push_notification(
                        resident["fcm_token"],
                        f"{visitor_name} just checked in for your unit.",
                        f"Hello! {visitor_name} has arrived to meet you",
                        {"event": "adoc_visitor_entry", "time": datetime.now().isoformat()}
                    )
                    print("Notification sent to resident:", notif)
                else:
                    print("No resident found or FCM token missing for this adoc_visitor.")

        return {"status": "stored" if activity_id else "skipped", "id": activity_id}

    except Exception as e:
        db.rollback()
        traceback.print_exc()
        return {"status": "error", "detail": str(e)}

# CAMERA_IP = "192.168.1.64"         
# CAMERA_USER = "admin"             
# CAMERA_PASS = "Psts@#12"            
# SERVER_IP = "192.168.1.94"        
# SERVER_PORT = 9000

# @router.post("/subscribe-camera")
# async def subscribe_camera():
#     url = f"http://{CAMERA_IP}/ISAPI/Event/notification/httpHosts/1"

#     payload = f"""
#     <HttpHostNotification>
#         <id>1</id>
#         <url>http://{SERVER_IP}:{SERVER_PORT}/hikvision/events</url>
#         <protocolType>HTTP</protocolType>
#         <addressingFormatType>ipaddress</addressingFormatType>
#         <ipAddress>{SERVER_IP}</ipAddress>
#         <portNo>{SERVER_PORT}</portNo>
#         <parameterFormatType>XML</parameterFormatType>
#         <httpAuthenticationMethod>none</httpAuthenticationMethod>
#     </HttpHostNotification>
#     """

#     async with httpx.AsyncClient() as client:
#         r = await client.put(
#             url,
#             auth=DigestAuth(CAMERA_USER, CAMERA_PASS), 
#             headers={"Content-Type": "application/xml"},
#             content=payload.strip().encode()
#         )

#     return {"status": r.status_code, "response": r.text}




# @router.get("/check-subscription")
# async def check_subscription():
#     url = f"http://{CAMERA_IP}/ISAPI/Event/notification/httpHosts"

#     async with httpx.AsyncClient() as client:
#         r = await client.get(
#             url,
#             auth=DigestAuth(CAMERA_USER, CAMERA_PASS)
#         )

#     return {
#         "status": r.status_code,
#         "response": r.text
#     }





    
EVENT_CODES = {
    # (5, 38): "Invalid time period",
    (5, 3): "Anti-passback",
    (5, 38): "Authenticated via Fingerprint",
    (5, 5): "Duress alarm",
    (5, 6): "Open door failed",
    (5, 7): "Door opened",
    (5, 8): "Permission Expired",
    (5, 9): "No Card No.Found",
    (5, 10): "Face authentication failed",
    (5, 11): "Card and face mismatch",
    (5, 15): "Permission expired",
    (5, 28): "Door Open Timed Out (Door Contact)",
    (5, 75): "Authenticated via Face",
    (5, 76): "Authentication via Face Failed",  
    (5, 39): "Authentication via Finger Failed",  
    (5, 77): "QR code usage exceeded",
    (5, 78): "QR code not in valid time range",
    (5, 79): "QR code doesn't exist",
    (5, 80): "Face not found in face group",
    (5, 81): "Card not found in card group",
    (2, 1024): "Device Powering On",
    (5, 27): "Device Abnormally Open (Door Contact)",
    (5, 21): "Door Unlocked",
    (5, 22): "Door Locked",
    (5, 1): "Authenticated via QR code",
    (3, 112): "Remote:Login",
    (3, 122): "Remote:Alarm Disarming",
    (3, 121): "Remote:Alarm Arming",
    (1, 1028): "Device Tampered",
}




# Your EVENT_CODES mapping should be defined somewhere
# EVENT_CODES = {(5, 1): "Some Event", ...}

@router.get("/device_activities")
def list_device_activities(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search by name"),
    sort: Optional[str] = Query(None, regex="^(recent|old|null)$"),
    building_id: Optional[int] = Query(None, description="Filter by building_id"),
    db: Session = Depends(get_db)
):
    try:
        offset = (page - 1) * per_page

        if sort == "recent":
            order_by = "created_at DESC"
        elif sort == "old":
            order_by = "created_at ASC"
        else:
            order_by = "created_at DESC"

        valid_card_nos = None
        if building_id:
            user_ids = db.execute(
                text("SELECT user_id FROM user_access_details WHERE building_id = :bid"),
                {"bid": building_id}
            ).fetchall()
            user_ids = [str(u.user_id) for u in user_ids]

            if user_ids:
                cards = db.execute(
                    text("SELECT card_no FROM user_personal_details WHERE id IN :uids"),
                    {"uids": tuple(user_ids)}
                ).fetchall()
                personal_cards = {c.card_no for c in cards if c.card_no}

                visitor_cards = db.execute(
                    text("SELECT card_no FROM  invite_visitor WHERE user_id IN :uids"),
                    {"uids": tuple(user_ids)}
                ).fetchall()
                visitor_cards = {v.card_no for v in visitor_cards if v.card_no}

                valid_card_nos = personal_cards.union(visitor_cards)
            else:
                valid_card_nos = set()

        total_count = db.execute(text("SELECT COUNT(*) FROM device_activities")).scalar()

        result = db.execute(
            text(f"""
                SELECT id, device_activities, created_at, updated_at
                FROM device_activities
                ORDER BY {order_by}
                LIMIT :limit OFFSET :offset
            """),
            {"limit": per_page, "offset": offset}
        )
        rows = result.fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail="No device activities found.")

        activities = []
        for row in rows:
            try:
                parsed_json = row.device_activities
                if isinstance(parsed_json, str):
                    parsed_json = json.loads(parsed_json)
            except json.JSONDecodeError:
                parsed_json = {"error": "Invalid JSON format"}

            if search and search.lower() not in parsed_json.get("name", "").lower():
                continue

            if building_id and valid_card_nos is not None:
                if parsed_json.get("cardNo") not in valid_card_nos:
                    continue

            major = parsed_json.get("majorEventType")
            sub = parsed_json.get("subEventType")
            event_title = EVENT_CODES.get((major, sub), "Unknown Event")

            activities.append({
                "id": row.id,
                "device_activities": parsed_json,
                "event_title": event_title,
                "created_at": row.created_at,
                "updated_at": row.updated_at
            })

        last_page = (total_count + per_page - 1) // per_page

        return {
            "status": 200,
            "message": f"Found {len(activities)} device activity record(s)",
            "data": activities,
            "pagination_details": {
                "page": page,
                "per_page": per_page,
                "total": total_count, 
                "last_page": last_page
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/get_activity_logs")
def get_visitor_activity_logs(
    request: Request,
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    card_no: Optional[str] = Query(None, description="Filter by card number"),
    visitor_name: Optional[str] = Query(None, description="Filter by visitor name"),
    from_date: Optional[str] = Query(None, description="Filter from this date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="Filter to this date (YYYY-MM-DD)"),
    event_type: Optional[str] = Query(None, description="Filter by event type (5=ACCESS_GRANTED, 6=ACCESS_DENIED)"),
    activity_type: Optional[str] = Query(None, description="Filter by activity type (visitor_card, vehicle_anpr)"),
    db: Session = Depends(get_db)
):
    """
    Get visitor activity logs from:
    1. device_activities (card-based visitors) - matches with invite_visitor by card_no
    2. anpr_device_activities (vehicle-based) - matches with license_plate_access by plate_number
    """
    try:
        ip_address = request.client.host if request and request.client else "Unknown"
        

        card_query = """
            SELECT 
                da.id as activity_id,
                da.device_activities,
                da.created_at as activity_created_at,
                da.updated_at as activity_updated_at,
                'card_visitor' as activity_source,
                iv.id as visitor_id,
                iv.name as visitor_name,
                iv.user_id,
                iv.visitor_id as visitor_unique_id,
                iv.purpose_visit,
                iv.card_no,
                iv.phone,
                iv.valid as visitor_validity,
                iv.qr_token,
                iv.created_at as visitor_created_at,
                iv.updated_at as visitor_updated_at,
                JSON_UNQUOTE(JSON_EXTRACT(da.device_activities, '$.majorEventType')) as major_event_type,
                JSON_UNQUOTE(JSON_EXTRACT(da.device_activities, '$.subEventType')) as sub_event_type,
                JSON_UNQUOTE(JSON_EXTRACT(da.device_activities, '$.userType')) as user_type,
                JSON_UNQUOTE(JSON_EXTRACT(da.device_activities, '$.deviceName')) as device_name,
                JSON_UNQUOTE(JSON_EXTRACT(da.device_activities, '$.dateTime')) as event_datetime,
                JSON_UNQUOTE(JSON_EXTRACT(da.device_activities, '$.cardType')) as card_type,
                JSON_UNQUOTE(JSON_EXTRACT(da.device_activities, '$.employeeNoString')) as employee_no,
                JSON_UNQUOTE(JSON_EXTRACT(da.device_activities, '$.name')) as event_name,
                NULL as plate_number,
                NULL as gate_status,
                NULL as channel_name,
                NULL as barrier_gate_ctrl_type,
                NULL as list_type,
                NULL as vehicle_entry_time,
                NULL as vehicle_exit_time,
                NULL as vehicle_type_id,
                NULL as vehicle_type_name,
                uad.id as user_access_id,
                uad.residency_type_id,
                uad.join_date,
                uad.access_start,
                uad.access_end,
                pb.id as building_id,
                pb.building_name,
                pb.address_number,
                pb.common as building_common,
                bl.id as level_id,
                bl.level as level_number,
                bl.total_unit as level_total_units,
                bu.id as unit_id,
                bu.unit_no,
                bu.unit_name
            FROM device_activities da
            INNER JOIN invite_visitor iv ON JSON_UNQUOTE(JSON_EXTRACT(da.device_activities, '$.cardNo')) = iv.card_no
            LEFT JOIN user_access_details uad ON iv.user_id = uad.user_id
            LEFT JOIN property_building pb ON uad.building_id = pb.id
            LEFT JOIN building_level bl ON uad.level_id = bl.id
            LEFT JOIN building_units bu ON uad.unit_id = bu.id
            WHERE 1=1
        """
        
        
        vehicle_query = """
            SELECT 
                aa.id as activity_id,
                aa.anpr_device_activity as device_activities,
                aa.created_at as activity_created_at,
                aa.updated_at as activity_updated_at,
                'vehicle_anpr' as activity_source,
                NULL as visitor_id,
                NULL as visitor_name,
                lpa.resident_id as user_id,
                NULL as visitor_unique_id,
                NULL as purpose_visit,
                NULL as card_no,
                NULL as phone,
                NULL as visitor_validity,
                NULL as qr_token,
                NULL as visitor_created_at,
                NULL as visitor_updated_at,
                NULL as major_event_type,
                NULL as sub_event_type,
                'vehicle' as user_type,
                NULL as device_name,
                JSON_UNQUOTE(JSON_EXTRACT(aa.anpr_device_activity, '$.dateTime')) as event_datetime,
                NULL as card_type,
                NULL as employee_no,
                NULL as event_name,
                JSON_UNQUOTE(JSON_EXTRACT(aa.anpr_device_activity, '$.plate_number')) as plate_number,
                JSON_UNQUOTE(JSON_EXTRACT(aa.anpr_device_activity, '$.gate_status')) as gate_status,
                JSON_UNQUOTE(JSON_EXTRACT(aa.anpr_device_activity, '$.channel_name')) as channel_name,
                JSON_UNQUOTE(JSON_EXTRACT(aa.anpr_device_activity, '$.barrier_gate_ctrl_type')) as barrier_gate_ctrl_type,
                JSON_UNQUOTE(JSON_EXTRACT(aa.anpr_device_activity, '$.list_type')) as list_type,
                aa.entry_time as vehicle_entry_time,
                aa.exit_time as vehicle_exit_time,
                lpa.vehicle_type as vehicle_type_id,
                vt.title as vehicle_type_name,
                uad.id as user_access_id,
                uad.residency_type_id,
                uad.join_date,
                uad.access_start,
                uad.access_end,
                pb.id as building_id,
                pb.building_name,
                pb.address_number,
                pb.common as building_common,
                bl.id as level_id,
                bl.level as level_number,
                bl.total_unit as level_total_units,
                bu.id as unit_id,
                bu.unit_no,
                bu.unit_name
            FROM anpr_device_activities aa
            INNER JOIN license_plate_access lpa ON JSON_UNQUOTE(JSON_EXTRACT(aa.anpr_device_activity, '$.plate_number')) = lpa.LicensePlate
            LEFT JOIN vehicle_type vt ON lpa.vehicle_type = vt.id
            LEFT JOIN user_access_details uad ON lpa.resident_id = uad.user_id
            LEFT JOIN property_building pb ON uad.building_id = pb.id
            LEFT JOIN building_level bl ON uad.level_id = bl.id
            LEFT JOIN building_units bu ON uad.unit_id = bu.id
            WHERE 1=1
        """
        
        params = {}
        
    
        card_where = []
        vehicle_where = []
        
        if user_id:
            card_where.append(" iv.user_id = :user_id")
            vehicle_where.append(" lpa.resident_id = :user_id")
            params["user_id"] = str(user_id)
        
        if card_no:
            card_where.append(" iv.card_no = :card_no")
            params["card_no"] = card_no
        
        if visitor_name:
            card_where.append(" iv.name LIKE :visitor_name")
            params["visitor_name"] = f"%{visitor_name}%"
        
        if from_date:
            card_where.append(" DATE(da.created_at) >= :from_date")
            vehicle_where.append(" DATE(aa.created_at) >= :from_date")
            params["from_date"] = from_date
        
        if to_date:
            card_where.append(" DATE(da.created_at) <= :to_date")
            vehicle_where.append(" DATE(aa.created_at) <= :to_date")
            params["to_date"] = to_date
        
        if event_type:
            card_where.append(" JSON_EXTRACT(da.device_activities, '$.majorEventType') = :event_type")
            
            if event_type == '5':
                vehicle_where.append(" JSON_UNQUOTE(JSON_EXTRACT(aa.anpr_device_activity, '$.gate_status')) LIKE '%OPENED%'")
            elif event_type == '6':
                vehicle_where.append(" JSON_UNQUOTE(JSON_EXTRACT(aa.anpr_device_activity, '$.gate_status')) LIKE '%DENIED%'")
            params["event_type"] = event_type
        
        # Add WHERE clauses to queries
        if card_where:
            card_query += " AND " + " AND ".join(card_where)
        
        if vehicle_where:
            vehicle_query += " AND " + " AND ".join(vehicle_where)
        
        if activity_type == 'visitor_card':
            vehicle_query += " AND 1=0"  
        elif activity_type == 'vehicle_anpr':
            card_query += " AND 1=0" 
        
        final_query = f"""
            SELECT * FROM (
                {card_query}
                UNION ALL
                {vehicle_query}
            ) AS combined_activities
            ORDER BY activity_created_at DESC
        """
        
        result = db.execute(text(final_query), params).mappings().all()
        
        activity_logs = []
        for row in result:
            visitor_validity = row.get('visitor_validity')
            if visitor_validity and isinstance(visitor_validity, str):
                import json
                try:
                    visitor_validity = json.loads(visitor_validity)
                except:
                    pass
            
            
            activity_source = row.get('activity_source', 'card_visitor')
            
            if activity_source == 'card_visitor':
                major_event = row.get('major_event_type')
                event_status = "UNKNOWN"
                if major_event == '5' or major_event == 5:
                    event_status = "ACCESS_GRANTED"
                elif major_event == '6' or major_event == 6:
                    event_status = "ACCESS_DENIED"
                elif major_event == '7' or major_event == 7:
                    event_status = "DOOR_OPEN"
                elif major_event == '8' or major_event == 8:
                    event_status = "DOOR_CLOSED"
                
                event_type_val = int(major_event) if major_event else None
                sub_event_type = int(row.get('sub_event_type')) if row.get('sub_event_type') else None
                
            else:  
                gate_status = row.get('gate_status', '')
                if gate_status and 'OPENED' in gate_status.upper():
                    event_status = "ACCESS_GRANTED"
                    event_type_val = 5
                elif gate_status and 'DENIED' in gate_status.upper():
                    event_status = "ACCESS_DENIED"
                    event_type_val = 6
                else:
                    event_status = "VEHICLE_PASS"
                    event_type_val = 5
                
                sub_event_type = None
            
            vehicle_entry_time = row.get('vehicle_entry_time')
            vehicle_exit_time = row.get('vehicle_exit_time')
            
            
            if vehicle_entry_time and vehicle_entry_time != '':
                if 'T' in str(vehicle_entry_time):
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(vehicle_entry_time.replace('+00:00', ''))
                        vehicle_entry_time = dt.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        pass
            else:
                vehicle_entry_time = None
            
            if vehicle_exit_time and vehicle_exit_time != '':
                if 'T' in str(vehicle_exit_time):
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(vehicle_exit_time.replace('+00:00', ''))
                        vehicle_exit_time = dt.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        pass
            else:
                vehicle_exit_time = None  
            
            
            event_datetime = row.get('event_datetime')
            if event_datetime:
                if 'T' in str(event_datetime):
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(event_datetime.replace('+00:00', ''))
                        event_datetime = dt.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        pass
            
            log_entry = {
                "activity_id": row['activity_id'],
                "activity_source": activity_source,
                "card_no": row.get('card_no'),
                "plate_number": row.get('plate_number'),
                "employee_no": row.get('employee_no'),
                "event_name": row.get('event_name'),
                "user_type": row.get('user_type'),
                "card_type": row.get('card_type'),
                "event_type": event_type_val,
                "event_status": event_status,
                "sub_event_type": sub_event_type,
                "device_name": row.get('device_name'),
                "gate_status": row.get('gate_status'),
                "channel_name": row.get('channel_name'),
                "barrier_gate_ctrl_type": row.get('barrier_gate_ctrl_type'),
                "list_type": row.get('list_type'),
                "event_datetime": event_datetime,
                "vehicle_entry_time": vehicle_entry_time,
                "vehicle_exit_time": vehicle_exit_time,  
                "vehicle_type_id": row.get('vehicle_type_id'),
                "vehicle_type_name": row.get('vehicle_type_name'),
                "activity_created_at": str(row['activity_created_at']) if row['activity_created_at'] else None,
                "activity_updated_at": str(row['activity_updated_at']) if row['activity_updated_at'] else None,
                
                "visitor_record_id": row.get('visitor_id'),
                "visitor_name": row.get('visitor_name'),
                "user_id": row.get('user_id'),
                "visitor_unique_id": row.get('visitor_unique_id'),
                "purpose_visit": row.get('purpose_visit'),
                "visitor_phone": row.get('phone'),
                "visitor_validity": visitor_validity,
                "qr_token": row.get('qr_token'),
                "visitor_created_at": str(row['visitor_created_at']) if row['visitor_created_at'] else None,
                "visitor_updated_at": str(row['visitor_updated_at']) if row['visitor_updated_at'] else None,
                
                "user_access_id": row.get('user_access_id'),
                "residency_type_id": row.get('residency_type_id'),
                "join_date": str(row['join_date']) if row['join_date'] else None,
                "access_start": str(row['access_start']) if row['access_start'] else None,
                "access_end": str(row['access_end']) if row['access_end'] else None,
                
                
                "building_id": row.get('building_id'),
                "block_name": row.get('building_name'),
                "building_address": row.get('address_number'),
                "building_common": row.get('building_common'),
                "level_id": row.get('level_id'),
                "level_number": row.get('level_number'),
                "level_total_units": row.get('level_total_units'),
                "unit_id": row.get('unit_id'),
                "unit_no": row.get('unit_no'),
                "unit_name": row.get('unit_name')
            }
        
            cleaned_entry = {}
            for k, v in log_entry.items():
                if k == "vehicle_exit_time":
                    cleaned_entry[k] = v
                elif v is not None:
                    cleaned_entry[k] = v
            
            activity_logs.append(cleaned_entry)
        
        response_data = {
            "message": "Activity logs retrieved successfully",
            "total_records": len(activity_logs),
            "data": activity_logs,
            "filters_applied": {
                "user_id": user_id,
                "card_no": card_no,
                "visitor_name": visitor_name,
                "from_date": from_date,
                "to_date": to_date,
                "event_type": event_type,
                "activity_type": activity_type
            },
            "status": 200
        }
        
        return response_data
        
    except HTTPException as he:
        raise he
    except Exception as e:
        error_message = str(e)
        write_to_server_log(f"Error in get_activity_logs: {error_message}")
        import traceback
        write_to_server_log(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error retrieving activity logs: {error_message}")