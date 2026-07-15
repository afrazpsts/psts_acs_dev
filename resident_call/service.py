from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect,Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import text
from DB.db import get_db
import uuid
from datetime import datetime, timedelta, timezone
import asyncio
from resident_call.firebase import sending_notifications
from resident_call.models import CallStartPayload,RejectPayload,OpenDoorPayload
import requests
from requests.auth import HTTPDigestAuth
from utils.security import decrypt_password
from typing import Optional
import traceback
import json
from typing import Dict, Set

# from .models import RejectPayload


router = APIRouter()
connections = {}  
print("Connected users at startup:", list(connections.keys()))


IST = timezone(timedelta(hours=5, minutes=30))

async def notify_user_ws(user_id: str, message: dict):
    ws = connections.get(user_id)
    if not ws:
        print(f"[WS DEBUG] WS not found for user {user_id}")
        return False
    try:
        print(f"[WS DEBUG] Sending WS message to {user_id}: {message}")
        await ws.send_json(message)
        return True
    except Exception as e:
        print(f"[WS ERROR] Failed to send WS to {user_id}: {e}")
        connections.pop(user_id, None)
        return False


@router.post("/call/start")
async def start_call(payload: CallStartPayload, db: Session = Depends(get_db)):
    print("Incoming payload:", payload.dict())

    call_id = str(uuid.uuid4())
    now = datetime.now(IST)
    print("Generated call_id:", call_id)
    print("Timestamp:", now)

    visitor = db.execute(
        text("SELECT id FROM  user_access_details WHERE unit_id = :unit_id"),
        {"unit_id": payload.unit_id}
    ).fetchone()
    print("Visitor row:", visitor)
    if not visitor:
        raise HTTPException(status_code=404, detail="Resident not found for this unit")

    access_rows = db.execute(
        text("SELECT user_id FROM user_access_details WHERE unit_id = :unit_id"),
        {"unit_id": payload.unit_id}
    ).fetchall()
    print("Access row:", access_rows)
    if not access_rows:
        raise HTTPException(status_code=404, detail="No access mapping found")

    user_ids = [row.user_id for row in access_rows]
    print("Resident user_ids:", user_ids)

    tokens = []
    active_user_ids = []
    for uid in user_ids:
        rows = db.execute(
            text("""
                SELECT id, fcm_token 
                FROM user_personal_details 
                WHERE id = :user_id AND is_active = 1
            """),
            {"user_id": uid}
        ).fetchall()

        for r in rows:
            if r.fcm_token:
                tokens.append(r.fcm_token)
            active_user_ids.append(r.id)

    print("Active user_ids:", active_user_ids)
    print("Active tokens to send notification:", tokens)

    try:
        db.execute(
            text("""
                INSERT INTO resident_call 
                (call_id, unit_id, delivery_id, building_id, level_id, purpose_of_visit, name,
                 status, answered_by, started_at, created_at, updated_at)
                VALUES (:call_id, :unit_id, :delivery_id, :building_id, :level_id, :purpose_of_visit, :name,
                        :status, NULL, :started_at, :created_at, :updated_at)
            """),
            {
                "call_id": call_id,
                "unit_id": payload.unit_id,
                "delivery_id": payload.delivery_id,
                "building_id": payload.building_id,
                "level_id": payload.level_id,
                "purpose_of_visit": payload.purpose_of_visit,
                "name": payload.name,
                "status": "ringing",
                "started_at": now,
                "created_at": now,
                "updated_at": now
            }
        )
        db.commit()
        print("Inserted call into resident_call table")
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Failed to insert call: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to insert call: {e}")

    if tokens:
        print("[DEBUG] Sending notifications via FCM...")
        sending_notifications(
            tokens,
            title="Incoming Call",
            body="Tap to answer",
            data={
                "call_id": call_id,
                "name": payload.name,
                "purpose_of_visit": payload.purpose_of_visit,
                "unit_id": payload.unit_id,
                "building_id": payload.building_id,
                "level_id": payload.level_id,
                "initiated_by": payload.delivery_id
            }
        )
        print("[DEBUG] Notifications sent")

    for uid in active_user_ids:
        if uid in connections:
            asyncio.create_task(notify_user_ws(uid, {
                "type": "incoming_call",
                "call_id": call_id,
                "unit_id": payload.unit_id,
                "initiated_by": payload.delivery_id,
            }))

    if payload.delivery_id in connections:
        asyncio.create_task(notify_user_ws(payload.delivery_id, {
            "type": "call-ringing",
            "call_id": call_id,
            "unit_id": payload.unit_id,
        }))

    print("Call start process complete for call_id:", call_id)
    return {"call_id": call_id, "status": "ringing"}


@router.websocket("/ws/signaling")
async def websocket_endpoint(ws: WebSocket, db: Session = Depends(get_db)):
    client_host = ws.client.host if ws.client else "unknown"
    print(f"[WS DEBUG] New connection from {client_host}")
    await ws.accept()
    user_id = None

    try:
        try:
            init = await ws.receive_json()
        except WebSocketDisconnect:
            print(f"[WS DEBUG] Client disconnected during registration from {client_host}")
            return
        except Exception as e:
            print(f"[WS ERROR] Failed to parse initial registration payload: {e}")
            await ws.close(code=4002)
            return

        if init.get("type") != "register" or not init.get("user_id"):
            print(f"[WS ERROR] Invalid registration payload: {init!r}")
            await ws.close(code=4001)
            return

        user_id = init["user_id"]
        connections[user_id] = ws
        print(f"[WS DEBUG] Registered WS user_id: {user_id}")
        print(f"[WS DEBUG] Current WS connections: {list(connections.keys())}")

        while True:
            try:
                msg = await ws.receive_json()
                print(f"[WS DEBUG] Received WS message from {user_id}: {msg!r}")
            except WebSocketDisconnect:
                print(f"[WS DEBUG] Client {user_id} disconnected")
                
                active_calls = db.execute(
                    text("""
                        SELECT call_id, delivery_id, answered_by 
                        FROM resident_call
                        WHERE status IN ('ringing','answered')
                          AND (delivery_id = :user OR answered_by = :user)
                    """),
                    {"user": user_id}
                ).fetchall()

                for call in active_calls:
                    door_opened = db.execute(
                        text("""
                            SELECT 1 FROM resident_call 
                            WHERE call_id = :call_id 
                            AND allow_access = 2
                        """),
                        {"call_id": call.call_id}
                    ).fetchone()
                    
                    if door_opened:
                        print(f"[WS INFO] Door was opened for call {call.call_id}, skipping hangup on disconnect")
                        
                        # Just update the call status to ended
                        db.execute(
                            text("""
                                UPDATE resident_call
                                SET status = 'ended', ended_at = :ended_at
                                WHERE call_id = :call_id
                                  AND status != 'ended'
                            """),
                            {"ended_at": datetime.now(IST), "call_id": call.call_id}
                        )
                        db.commit()
                    else:
                        db.execute(
                            text("""
                                UPDATE resident_call
                                SET status = 'ended', ended_at = :ended_at
                                WHERE call_id = :call_id
                                  AND status != 'ended'
                            """),
                            {"ended_at": datetime.now(IST), "call_id": call.call_id}
                        )
                        db.commit()

                        participants = set()
                        if call.delivery_id:
                            participants.add(call.delivery_id)
                        if call.answered_by:
                            participants.add(call.answered_by)

                        for u in participants:
                            if u in connections and u != user_id:
                                await notify_user_ws(u, {
                                    "type": "hangup", 
                                    "call_id": call.call_id, 
                                    "from": user_id,
                                    "reason": "disconnected"
                                })

                connections.pop(user_id, None)
                break
            except Exception as e:
                print(f"[WS ERROR] Failed to parse WS message from {user_id}: {e}")
                break

            mtype = msg.get("type")
            print(f"[WS DEBUG] Message type: {mtype}")

            if mtype == "call-accept":
                call_id = msg.get("call_id")
                from_id = user_id

                result = db.execute(
                    text("""
                        UPDATE resident_call
                        SET answered_by = :answered_by,
                            answered_at = :answered_at,
                            status = 'answered'
                        WHERE call_id = :call_id
                          AND status = 'ringing'
                          AND answered_by IS NULL
                    """),
                    {"answered_by": from_id, "answered_at": datetime.now(IST), "call_id": call_id}
                )
                db.commit()

                if result.rowcount == 0:
                    await ws.send_json({"type": "call-already-picked", "call_id": call_id})
                    continue

                delivery_row = db.execute(
                    text("SELECT delivery_id, unit_id, notified_users FROM resident_call WHERE call_id = :call_id"),
                    {"call_id": call_id}
                ).fetchone()
                delivery_id = delivery_row.delivery_id if delivery_row else None
                unit_id = delivery_row.unit_id if delivery_row else None

                notified_list = []
                if delivery_row and delivery_row.notified_users:
                    try:
                        notified_list = json.loads(delivery_row.notified_users)
                    except Exception:
                        notified_list = []

                if delivery_id:
                    await notify_user_ws(delivery_id, {
                        "type": "webrtc-offer-request",
                        "call_id": call_id,
                        "from": from_id
                    })

                other_residents = db.execute(
                    text("""
                        SELECT uad.user_id, upd.first_name, upd.fcm_token
                        FROM user_access_details uad
                        LEFT JOIN user_personal_details upd ON uad.user_id = upd.id
                        WHERE uad.unit_id = :unit_id
                          AND uad.user_id != :answered_by
                    """),
                    {"unit_id": unit_id, "answered_by": from_id}
                ).fetchall()

                answered_first_name = db.execute(
                    text("SELECT first_name FROM user_personal_details WHERE id = :answered_by"),
                    {"answered_by": from_id}
                ).scalar() or "Someone"

                notified_list_updated = []

                for r in other_residents:
                    notified = False

                    if r.user_id in connections:
                        await notify_user_ws(r.user_id, {
                            "type": "call-cancel",
                            "call_id": call_id,
                            "from": from_id,
                            "body": f"{answered_first_name} has taken the call"
                        })
                        notified = True

                    if r.fcm_token:
                        sending_notifications([r.fcm_token],
                                              title="Call Accepted",
                                              body=f"{answered_first_name} has taken the call")
                        notified = True

                    if notified:
                        notified_list_updated.append({
                            "user_id": r.user_id,
                            "message": f"{answered_first_name} has taken the call"
                        })

                notified_list.extend(notified_list_updated)

                db.execute(
                    text("UPDATE resident_call SET notified_users = :users WHERE call_id = :call_id"),
                    {"users": json.dumps(notified_list), "call_id": call_id}
                )
                db.commit()

                await ws.send_json({
                    "type": "call-accepted-confirm",
                    "call_id": call_id,
                    "you": from_id,
                    "body": "You have accepted the call"
                })

            elif mtype == "door-access-request":
                call_id = msg.get("call_id")
                
                call_row = db.execute(
                    text("SELECT delivery_id, answered_by, unit_id FROM resident_call WHERE call_id = :call_id"),
                    {"call_id": call_id}
                ).fetchone()
                
                if not call_row:
                    await ws.send_json({"type": "error", "message": "Call not found"})
                    continue
                
                if call_row.delivery_id and call_row.delivery_id in connections:
                    await notify_user_ws(call_row.delivery_id, {
                        "type": "door-access-requested",
                        "call_id": call_id,
                        "requested_by": user_id, 
                        "timestamp": datetime.now(IST).isoformat(),
                        "message": "Resident has requested to open the door"
                    })
                    
                    await ws.send_json({
                        "type": "door-access-request-sent",
                        "call_id": call_id,
                        "to": call_row.delivery_id,
                        "message": "Door access request sent to delivery person"
                    })
                else:
                    await ws.send_json({
                        "type": "door-access-request-failed",
                        "call_id": call_id,
                        "message": "Delivery person not connected"
                    })

            elif mtype == "door-access-granted":
                call_id = msg.get("call_id")
                
                call_row = db.execute(
                    text("SELECT delivery_id, answered_by FROM resident_call WHERE call_id = :call_id"),
                    {"call_id": call_id}
                ).fetchone()
                
                if not call_row:
                    await ws.send_json({"type": "error", "message": "Call not found"})
                    continue
                
                answered_by = call_row.answered_by
                if answered_by and answered_by in connections:
                    await notify_user_ws(answered_by, {
                        "type": "door-access-granted",
                        "call_id": call_id,
                        "granted_by": user_id,  
                        "timestamp": datetime.now(IST).isoformat(),
                        "message": "Delivery person has granted door access permission"
                    })
                    
                    await ws.send_json({
                        "type": "door-access-granted-confirm",
                        "call_id": call_id,
                        "to": answered_by,
                        "message": "Door access permission sent to resident"
                    })
                else:
                    await ws.send_json({
                        "type": "door-access-granted-failed",
                        "call_id": call_id,
                        "message": "Resident not connected"
                    })

            elif mtype in ["offer", "answer", "ice-candidate"]:
                to_id = msg.get("to")
                if not to_id:
                    await ws.send_json({"type": "error", "message": "missing 'to'"})
                    continue
                forward_msg = {**msg, "from": user_id}
                await notify_user_ws(to_id, forward_msg)

            elif mtype == "hangup":
                call_id = msg.get("call_id")
                reason = msg.get("reason", "manual")
                
                door_was_opened = db.execute(
                    text("""
                        SELECT 1 FROM resident_call 
                        WHERE call_id = :call_id 
                        AND allow_access = 2
                    """),
                    {"call_id": call_id}
                ).fetchone()
                
                if door_was_opened:
                    print(f"[WS INFO] Door was opened for call {call_id}, skipping hangup message")
                    
                    db.execute(
                        text("""
                            UPDATE resident_call
                            SET status = 'ended', ended_at = :ended_at
                            WHERE call_id = :call_id
                              AND status != 'ended'
                        """),
                        {"ended_at": datetime.now(IST), "call_id": call_id}
                    )
                    db.commit()
                else:
                    db.execute(
                        text("""
                            UPDATE resident_call
                            SET status = 'ended', ended_at = :ended_at
                            WHERE call_id = :call_id
                              AND status != 'ended'
                        """),
                        {"ended_at": datetime.now(IST), "call_id": call_id}
                    )
                    db.commit()

                    call_row = db.execute(
                        text("SELECT delivery_id, answered_by FROM resident_call WHERE call_id = :call_id"),
                        {"call_id": call_id}
                    ).fetchone()

                    participants = set()
                    if call_row:
                        if call_row.delivery_id:
                            participants.add(call_row.delivery_id)
                        if call_row.answered_by:
                            participants.add(call_row.answered_by)

                    for u in participants:
                        if u in connections and u != user_id:
                            await notify_user_ws(u, {
                                "type": "hangup", 
                                "call_id": call_id, 
                                "from": user_id,
                                "reason": reason
                            })

            elif mtype == "call-end-after-door":
                call_id = msg.get("call_id")
                
                db.execute(
                    text("""
                        UPDATE resident_call
                        SET status = 'ended', ended_at = :ended_at
                        WHERE call_id = :call_id
                          AND status != 'ended'
                    """),
                    {"ended_at": datetime.now(IST), "call_id": call_id}
                )
                db.commit()
                
                print(f"[WS INFO] Call {call_id} ended after door was opened")

            else:
                print(f"[WS WARNING] Unknown WS message type from {user_id}: {msg!r}")

    except Exception as e:
        print(f"[WS ERROR] Exception in WebSocket handler for {user_id}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if user_id and user_id in connections:
            connections.pop(user_id, None)
            print(f"[WS DEBUG] Cleaned up WS connection for {user_id}")


@router.post("/reject")
def reject_call(payload: RejectPayload, db: Session = Depends(get_db)):
    try:
        row = db.execute(
            text("SELECT rejected_by FROM resident_call WHERE call_id = :call_id"),
            {"call_id": payload.call_id}
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Call not found")

        current_rejected = []
        if row.rejected_by:
            try:
                current_rejected = json.loads(row.rejected_by)
            except Exception:
                current_rejected = []

        new_entry = {
            "user_id": payload.rejected_by,
            "reject_at": datetime.now().isoformat(),
            "status": "rejected"
        }
        current_rejected.append(new_entry)

        db.execute(
            text("""
                UPDATE resident_call
                SET rejected_by = :rejected_by,
                    updated_at = :updated_at
                WHERE call_id = :call_id
            """),
            {
                "rejected_by": json.dumps(current_rejected),
                "updated_at": datetime.now(),
                "call_id": payload.call_id
            }
        )
        db.commit()

        return {
            "success": True,
            "title": "rejected",
            "call_id": payload.call_id,
            "rejected_by": current_rejected
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/open_door/{kiosk_id}")
async def open_door(
    kiosk_id: int,
    payload: OpenDoorPayload,  
    door_id: int = 1,
    db: Session = Depends(get_db)
):
    call_id = payload.call_id

    call_info = db.execute(
        text("""
            SELECT delivery_id, answered_by, unit_id, status 
            FROM resident_call 
            WHERE call_id = :call_id
        """),
        {"call_id": call_id}
    ).fetchone()
    
    if not call_info:
        raise HTTPException(status_code=404, detail=f"No active call found with call_id {call_id}")
    
    delivery_id = call_info.delivery_id
    answered_by = call_info.answered_by
    unit_id = call_info.unit_id
    
    opener_id = answered_by or delivery_id
    
    query = text("SELECT ip, user_name, password FROM camera_devices WHERE kiosk_id = :kiosk_id")
    result = db.execute(query, {"kiosk_id": kiosk_id}).fetchone()
    if not result:
        raise HTTPException(status_code=404, detail=f"No device found for kiosk_id {kiosk_id}")

    updated = db.execute(
        text("""
            UPDATE resident_call
            SET allow_access = 2, updated_at = :now
            WHERE call_id = :call_id
        """),
        {"call_id": call_id, "now": datetime.now(IST)}
    )
    db.commit()

    if updated.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"No active call found with call_id {call_id}")

    device_ip = result.ip
    username = result.user_name
    password = decrypt_password(result.password)

    url = f"http://{device_ip}/ISAPI/AccessControl/RemoteControl/door/{door_id}"
    headers = {"Content-Type": "application/xml"}
    data = '<RemoteControlDoor><cmd>open</cmd></RemoteControlDoor>'

    try:
        response = requests.put(
            url,
            headers=headers,
            data=data,
            auth=HTTPDigestAuth(username, password),
            timeout=5
        )

        door_status = "success" if response.status_code == 200 else "failed"
        door_message = f"Door {door_id} opened successfully on kiosk {kiosk_id}" if response.status_code == 200 else f"Failed to open door: {response.text}"

        participants: Set[str] = set()
        
        if delivery_id:
            participants.add(delivery_id)
        
        if answered_by:
            participants.add(answered_by)
        
        if unit_id and door_status == "success":
            other_residents = db.execute(
                text("""
                    SELECT uad.user_id
                    FROM user_access_details uad
                    WHERE uad.unit_id = :unit_id
                      AND uad.user_id NOT IN (:delivery_id, :answered_by)
                """),
                {"unit_id": unit_id, "delivery_id": delivery_id, "answered_by": answered_by}
            ).fetchall()
            
            for resident in other_residents:
                participants.add(resident.user_id)
        
        notification_tasks = []
        for participant in participants:
            notification_tasks.append(
                notify_user_ws(participant, {
                    "type": "door-status",
                    "call_id": call_id,
                    "door_status": door_status,
                    "message": door_message,
                    "opened_by": opener_id,
                    "timestamp": datetime.now(IST).isoformat(),
                    "kiosk_id": kiosk_id,
                    "door_id": door_id
                })
            )
        
        if notification_tasks:
            import asyncio
            await asyncio.gather(*notification_tasks)
        
        if response.status_code == 200:
            return {
                "status": "success",
                "message": door_message,
                "call_id": call_id,
                "allow_access": 2,
                "notified_participants": list(participants)
            }
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)

    except requests.RequestException as e:
        participants = set()
        if delivery_id:
            participants.add(delivery_id)
        if answered_by:
            participants.add(answered_by)
        
        notification_tasks = []
        for participant in participants:
            notification_tasks.append(
                notify_user_ws(participant, {
                    "type": "door-status",
                    "call_id": call_id,
                    "door_status": "error",
                    "message": f"Failed to open door: {str(e)}",
                    "opened_by": opener_id,
                    "timestamp": datetime.now(IST).isoformat(),
                    "kiosk_id": kiosk_id,
                    "door_id": door_id
                })
            )
        
        if notification_tasks:
            import asyncio
            await asyncio.gather(*notification_tasks)
        
        raise HTTPException(status_code=500, detail=str(e))
    

@router.get("/list")
def list_resident_calls(
    answered_by: Optional[str] = Query(None, description="Filter by answered_by (also checks rejected_by JSON)"),
    search: Optional[str] = Query(None, description="Search by call_id or delivery_id"),
    sort: Optional[str] = Query("recent", description="'recent' or 'old'"),
    db: Session = Depends(get_db)
):
    try:
        thirty_days_ago = datetime.now() - timedelta(days=30)

        filters = ["rc.created_at >= :start_date"]
        params = {"start_date": thirty_days_ago}

        if search:
            filters.append("(rc.call_id LIKE :search OR rc.delivery_id LIKE :search)")
            params["search"] = f"%{search}%"

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        order_clause = "ORDER BY rc.created_at DESC" if sort != "old" else "ORDER BY rc.created_at ASC"

        query = text(f"""
            SELECT rc.call_id, rc.delivery_id, rc.unit_id, rc.building_id, rc.level_id,
                   rc.purpose_of_visit, rc.name, rc.started_at, rc.ended_at, 
                   rc.answered_by, rc.answered_at, rc.status, rc.rejected_by, rc.allow_access,
                   rc.notified_users
            FROM resident_call rc
            {where_clause}
            {order_clause}
        """)

        rows = db.execute(query, params).fetchall()

        data = []
        for row in rows:
            rejected_list = []
            if row.rejected_by:
                try:
                    rejected_list = json.loads(row.rejected_by)
                except Exception:
                    rejected_list = []

            notified_list = []
            if row.notified_users:
                try:
                    notified_list = json.loads(row.notified_users)
                except Exception:
                    notified_list = []

            include_record = True
            record_status = row.status
            rejected_user_ids = [str(entry.get("user_id")) for entry in rejected_list]

            user_pickup = None
            if answered_by:
                for n in notified_list:
                    if str(n.get("user_id")) == str(answered_by):
                        user_pickup = n.get("message")
                        record_status = "notified"  
                        break

            if answered_by:
                if str(answered_by) in rejected_user_ids:
                    record_status = "cancelled"
                elif str(row.answered_by) == str(answered_by):
                    record_status = "accepted" if row.allow_access == 2 else "denied"
                elif user_pickup:  
                    record_status = "notified"
                else:
                    record_status = row.status

                include_record = (
                    str(row.answered_by) == str(answered_by) or 
                    str(answered_by) in rejected_user_ids or
                    user_pickup is not None
                )
            else:
                if row.answered_by:
                    record_status = "accepted" if row.allow_access == 2 else "denied"
                elif rejected_list:
                    record_status = "cancelled"
                elif notified_list:
                    record_status = "notified"
                else:
                    record_status = row.status

            if include_record:
                data.append({
                    "call_id": row.call_id,
                    "delivery_id": row.delivery_id,
                    "unit_id": row.unit_id,
                    "building_id": row.building_id,
                    "level_id": row.level_id,
                    "purpose_of_visit": row.purpose_of_visit,
                    "name": row.name,
                    "started_at": row.started_at,
                    "ended_at": row.ended_at,
                    "answered_by": row.answered_by,
                    "answered_at": row.answered_at,
                    "status": record_status,
                    "pickup": user_pickup, 
                    "rejected_by": rejected_list,
                    "allow_access": row.allow_access,
                    "notified_users": notified_list
                })

        return {"status_code": 201, "data": data, "total": len(data)}

    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal Server Error")