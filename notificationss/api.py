from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from .firebase_service import send_push_notification, send_push_notification_with_preference, send_bulk_notification_to_all_users
from DB.db import get_db
from datetime import datetime

router = APIRouter(prefix="/notifications")

class NotificationPayload(BaseModel):
    token: str
    title: str
    body: str
    data: dict = None

class NotificationWithPreferencePayload(BaseModel):
    user_id: int
    title: str
    body: str
    notification_type: str  # 'activities', 'announcements', 'marketing', etc.
    data: dict = None

class BulkNotificationPayload(BaseModel):
    title: str
    body: str
    notification_type: str  # 'activities', 'announcements', 'marketing', etc.
    data: dict = None

class TestNotificationPayload(BaseModel):
    notification_type: str  # 'activities', 'announcements', 'marketing', 'management', etc.
    title: Optional[str] = "Test Notification"
    body: Optional[str] = "This is a test notification message"
    user_id: Optional[int] = None  # If provided, test for single user, else test for all users

@router.post("/send")
def send_notification(payload: NotificationPayload):
    """Send notification without preference check (direct send)"""
    result = send_push_notification(payload.token, payload.title, payload.body, payload.data)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["response"])
    return {"status": 200, "message": "Notification sent successfully", "response": result["response"]}

@router.post("/send-with-preference")
def send_notification_with_preference(
    payload: NotificationWithPreferencePayload,
    db: Session = Depends(get_db)
):
    """Send notification with user preference check"""
    result = send_push_notification_with_preference(
        db=db,
        user_id=payload.user_id,
        title=payload.title,
        body=payload.body,
        notification_type=payload.notification_type,
        data=payload.data
    )
    
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result.get("reason", "Unknown error"))
    
    return result

@router.post("/send-to-all")
def send_to_all_users(
    payload: BulkNotificationPayload,
    db: Session = Depends(get_db)
):
    """Send notification to all users who have this notification type enabled"""
    result = send_bulk_notification_to_all_users(
        db=db,
        title=payload.title,
        body=payload.body,
        notification_type=payload.notification_type,
        data=payload.data
    )
    
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("reason", "Unknown error"))
    
    return result

@router.post("/test")
def test_notification(
    payload: TestNotificationPayload,
    db: Session = Depends(get_db)
):
    """
    Test API to check notification preferences and sending
    """
    try:
        from sqlalchemy import text
        
        test_data = {
            "test": "true",
            "timestamp": datetime.now().isoformat(),
            "type": payload.notification_type
        }
        
        # First, check what's in the database
        all_users_check = db.execute(text("""
            SELECT id, email, fcm_token, is_active,
                   CASE WHEN fcm_token IS NOT NULL AND fcm_token != '' THEN 'YES' ELSE 'NO' END as has_token
            FROM user_personal_details 
            WHERE is_active = 1
            ORDER BY id
        """)).fetchall()
        
        print("=== Database Check ===")
        for user in all_users_check:
            print(f"User {user[0]}: has_token={user[4]}, token={user[2][:30] if user[2] else 'NULL'}")
        
        preference_column_map = {
            'management': 'management_alert',
            'activities': 'activities_alert',
            'device_management': 'device_management_alert',
            'reports': 'reports_alert',
            'invoices': 'invoices_alert',
            'announcements': 'announcements_alert',
            'marketing': 'marketing_alert',
            'vehicle': 'vehicle_alert',
        }
        
        column_name = preference_column_map.get(payload.notification_type)
        if not column_name:
            raise HTTPException(status_code=400, detail=f"Invalid notification type: {payload.notification_type}")
        
        # Test for specific user
        if payload.user_id:
            # First check if user exists and has token
            user_check = db.execute(
                text("""
                    SELECT id, email, fcm_token, COALESCE({}, 1) as preference_enabled
                    FROM user_personal_details 
                    WHERE id = :user_id AND is_active = 1
                """.format(column_name)),
                {"user_id": payload.user_id}
            ).fetchone()
            
            if not user_check:
                return {
                    "status": "error",
                    "message": f"User {payload.user_id} not found or inactive"
                }
            
            result = send_push_notification_with_preference(
                db=db,
                user_id=payload.user_id,
                title=f"[TEST] {payload.title}",
                body=f"{payload.body}\n\nTest notification for {payload.notification_type} alerts",
                notification_type=payload.notification_type,
                data=test_data
            )
            
            return {
                "status": "test_completed",
                "test_type": "single_user",
                "user_id": payload.user_id,
                "user_info": {
                    "email": user_check[1],
                    "has_fcm_token": user_check[2] is not None and user_check[2] != '',
                    "preference_enabled": bool(user_check[3])
                },
                "notification_type": payload.notification_type,
                "result": result,
                "message": result.get("status") == "success" and "Notification sent successfully" or 
                          (result.get("status") == "skipped" and f"Notification skipped: {result.get('reason')}" or 
                           f"Error: {result.get('reason')}")
            }
        
        # Test for all users
        else:
            # Get all users with valid FCM tokens
            users_with_tokens = db.execute(
                text("""
                    SELECT id, email, fcm_token, COALESCE({}, 1) as preference_enabled
                    FROM user_personal_details 
                    WHERE is_active = 1 
                    AND fcm_token IS NOT NULL 
                    AND fcm_token != ''
                """.format(column_name))
            ).fetchall()
            
            print(f"Found {len(users_with_tokens)} users with valid FCM tokens")
            
            if len(users_with_tokens) == 0:
                # Show all users and their token status
                all_users = db.execute(text("""
                    SELECT id, email, 
                           CASE WHEN fcm_token IS NULL THEN 'NULL' 
                                WHEN fcm_token = '' THEN 'EMPTY' 
                                ELSE 'HAS_TOKEN' END as token_status
                    FROM user_personal_details 
                    WHERE is_active = 1
                """)).fetchall()
                
                return {
                    "status": "error",
                    "message": "No users with valid FCM tokens found",
                    "debug_info": {
                        "total_active_users": len(all_users),
                        "users_token_status": [{"id": u[0], "email": u[1], "token_status": u[2]} for u in all_users]
                    }
                }
            
            # Send notifications
            results = []
            sent_count = 0
            skipped_count = 0
            
            for user in users_with_tokens:
                if user[3]:  # If preference enabled
                    result = send_push_notification(
                        fcm_token=user[2],
                        title=f"[TEST] {payload.title}",
                        body=f"{payload.body}\n\nTest notification for {payload.notification_type} alerts",
                        data=test_data
                    )
                    results.append({
                        "user_id": user[0],
                        "email": user[1],
                        "preference_enabled": True,
                        "result": result
                    })
                    if result["status"] == "success":
                        sent_count += 1
                    else:
                        skipped_count += 1
                else:
                    results.append({
                        "user_id": user[0],
                        "email": user[1],
                        "preference_enabled": False,
                        "result": {"status": "skipped", "reason": f"User disabled {payload.notification_type} notifications"}
                    })
                    skipped_count += 1
            
            return {
                "status": "test_completed",
                "test_type": "all_users",
                "notification_type": payload.notification_type,
                "statistics": {
                    "total_active_users_with_tokens": len(users_with_tokens),
                    "users_will_receive": len([u for u in users_with_tokens if u[3]]),
                    "users_disabled_preference": len([u for u in users_with_tokens if not u[3]])
                },
                "test_results": {
                    "sent_successfully": sent_count,
                    "skipped_or_failed": skipped_count
                },
                "detailed_results": results[:5],  # Show first 5 results
                "message": f"Test completed. {sent_count} users received test notification, {skipped_count} users skipped."
            }
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in test notification: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/preference-stats")
def get_preference_statistics(db: Session = Depends(get_db)):
    """Get statistics about user notification preferences (for testing/debugging)"""
    from sqlalchemy import text
    
    result = db.execute(text("""
        SELECT 
            COUNT(*) as total_users,
            SUM(CASE WHEN fcm_token IS NOT NULL THEN 1 ELSE 0 END) as users_with_token,
            SUM(CASE WHEN COALESCE(management_alert, 1) = 1 THEN 1 ELSE 0 END) as management_enabled,
            SUM(CASE WHEN COALESCE(activities_alert, 1) = 1 THEN 1 ELSE 0 END) as activities_enabled,
            SUM(CASE WHEN COALESCE(device_management_alert, 1) = 1 THEN 1 ELSE 0 END) as device_management_enabled,
            SUM(CASE WHEN COALESCE(reports_alert, 1) = 1 THEN 1 ELSE 0 END) as reports_enabled,
            SUM(CASE WHEN COALESCE(invoices_alert, 1) = 1 THEN 1 ELSE 0 END) as invoices_enabled,
            SUM(CASE WHEN COALESCE(announcements_alert, 1) = 1 THEN 1 ELSE 0 END) as announcements_enabled,
            SUM(CASE WHEN COALESCE(marketing_alert, 1) = 1 THEN 1 ELSE 0 END) as marketing_enabled,
            SUM(CASE WHEN COALESCE(vehicle_alert, 1) = 1 THEN 1 ELSE 0 END) as vehicle_enabled
        FROM user_personal_details 
        WHERE is_active = 1
    """)).fetchone()
    
    return {
        "status": 200,
        "data": {
            "total_active_users": result[0],
            "users_with_fcm_token": result[1],
            "preferences": {
                "management_alert": result[2],
                "activities_alert": result[3],
                "device_management_alert": result[4],
                "reports_alert": result[5],
                "invoices_alert": result[6],
                "announcements_alert": result[7],
                "marketing_alert": result[8],
                "vehicle_alert": result[9]
            }
        }
    }