import firebase_admin
from firebase_admin import credentials, messaging
import os
from sqlalchemy import text
from typing import Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Check for environment variable first, then fallback to local file
cred_path = os.environ.get("FIREBASE_CREDENTIALS_PATH", os.path.join(BASE_DIR, "accountkey.json"))

# Initialize Firebase only once
if not firebase_admin._apps:
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)

def send_push_notification(fcm_token: str, title: str, body: str, data: dict = None):
    """Original function - sends without preference check"""
    message = messaging.Message(
        token=fcm_token,
        notification=messaging.Notification(title=title, body=body),
        data=data or {}
    )
    print("Sending notification to token:", fcm_token)

    try:
        response = messaging.send(message)
        return {"status": "success", "response": response}
    except Exception as e:
        return {"status": "error", "response": str(e)}

def send_push_notification_with_preference(
    db,  
    user_id: int, 
    title: str, 
    body: str, 
    notification_type: str,
    data: dict = None
):
    """
    Send push notification only if user has enabled that notification type
    
    notification_type options:
    - 'management' -> management_alert
    - 'activities' -> activities_alert  
    - 'device_management' -> device_management_alert
    - 'reports' -> reports_alert
    - 'invoices' -> invoices_alert
    - 'announcements' -> announcements_alert
    - 'marketing' -> marketing_alert
    - 'vehicle' -> vehicle_alert
    """
    try:
        user = db.execute(
            text("""
                SELECT fcm_token, 
                       COALESCE(management_alert, 1) as management_alert,
                       COALESCE(activities_alert, 1) as activities_alert,
                       COALESCE(device_management_alert, 1) as device_management_alert,
                       COALESCE(reports_alert, 1) as reports_alert,
                       COALESCE(invoices_alert, 1) as invoices_alert,
                       COALESCE(announcements_alert, 1) as announcements_alert,
                       COALESCE(marketing_alert, 1) as marketing_alert,
                       COALESCE(vehicle_alert, 1) as vehicle_alert
                FROM user_personal_details 
                WHERE id = :user_id AND is_active = 1
            """),
            {"user_id": user_id}
        ).fetchone()
        
        if not user:
            return {"status": "skipped", "reason": f"User {user_id} not found or inactive"}
        
        if not user[0]: 
            return {"status": "skipped", "reason": f"No FCM token found for user {user_id}"}
        
        fcm_token = user[0]
        
        preference_map = {
            'management': 1,      
            'activities': 2,      
            'device_management': 3,  
            'reports': 4,        
            'invoices': 5,        
            'announcements': 6,   
            'marketing': 7,       
            'vehicle': 8,         
        }
        
        pref_index = preference_map.get(notification_type)
        if pref_index is None:
            return {"status": "error", "reason": f"Invalid notification type: {notification_type}"}
        
        is_enabled = user[pref_index]  
        
        if not is_enabled:
            return {"status": "skipped", "reason": f"User {user_id} disabled {notification_type} notifications"}
        
        result = send_push_notification(fcm_token, title, body, data)
        return result
        
    except Exception as e:
        return {"status": "error", "reason": str(e), "user_id": user_id}

def send_bulk_notification_to_all_users(
    db,
    title: str,
    body: str,
    notification_type: str,
    data: dict = None
):
    """
    Send notifications to ALL users who have this notification type enabled
    """
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
    
    column_name = preference_column_map.get(notification_type)
    if not column_name:
        return {"status": "error", "reason": f"Invalid notification type: {notification_type}"}
    
    print(f"Checking users with {column_name} enabled and fcm_token not null")
    
    users = db.execute(
        text(f"""
            SELECT id, fcm_token, email
            FROM user_personal_details 
            WHERE is_active = 1 
            AND fcm_token IS NOT NULL 
            AND fcm_token != ''
            AND COALESCE({column_name}, 1) = 1
        """)
    ).fetchall()
    
    print(f"Found {len(users)} users with FCM token and {notification_type} enabled")
    for user in users:
        print(f"User ID: {user[0]}, Email: {user[2]}, Token: {user[1][:50]}...")
    
    results = []
    for user in users:
        result = send_push_notification_with_preference(
            db=db,
            user_id=user[0],
            title=title,
            body=body,
            notification_type=notification_type,
            data=data
        )
        results.append({
            "user_id": user[0],
            "email": user[2],
            "result": result
        })
    
    return {
        "total_users": len(users),
        "notification_type": notification_type,
        "results": results
    }