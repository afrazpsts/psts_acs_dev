from fastapi import APIRouter, Depends, UploadFile, Form,HTTPException, Request,Body
from sqlalchemy.orm import Session
from sqlalchemy import text
from activity_logs.service import log_activity
from common.logger import log as write_to_server_log
import traceback
from DB.db import get_db
from .service import create_marketing_service, list_announcements_service, list_marketing_service,delete_marketing_service, update_announcement_active_status_service,update_marketing_service,new_list_marketing_service,new_listing_marketing_service,list_marketing_search,generate_pdf_response,generate_excel_response
from utils.security import verify_token
from typing import Optional
from fastapi import Query
from typing import List
from datetime import datetime, date, timedelta
import json





router = APIRouter()

@router.post("/create_marketing")
async def create_marketing(
    request: Request,
    creator_email: Optional[str] = Form(None, description="Email of the person creating the marketing record"),
    status_id: int = Form(3),
    marketing_type_id: Optional[int] = Form(None), 
    announcement_type: int = Form(None), 
    property_id: int = Form(None),
    common_area_id: Optional[int] = Form(None),
    address: str = Form(None),
    phone: str = Form(None),
    country_code: str = Form(None),
    email: str = Form(None),
    title: str = Form(...),
    subtext: str = Form(None),
    description: str = Form(None),
    duration_start_date: str = Form(None),
    duration_end_date: str = Form(None),
    duration_from_time: str = Form(None),
    duration_end_time: str = Form(None),
    location_name: str = Form(None),
    map_link: str = Form(None),
    website: str = Form(None),
    terms_condition: str = Form(None),
    start_date: str = Form(None),
    end_date: str = Form(None),
    cover_image: UploadFile = Form(...),
    send_notification: bool = Form(True),  # New parameter to control notification sending
    db: Session = Depends(get_db)
):
    try:
        ip_address = request.client.host if request and request.client else "Unknown"
        
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
        
        result = create_marketing_service(
            db=db,
            status_id=status_id,
            marketing_type_id=marketing_type_id,
            announcement_type=announcement_type,
            property_id=property_id,
            common_area_id=common_area_id,
            address=address,
            phone=phone,
            country_code=country_code,
            email=email,
            title=title,
            subtext=subtext,
            description=description,
            duration_start_date=duration_start_date,
            duration_end_date=duration_end_date,
            duration_from_time=duration_from_time,
            duration_end_time=duration_end_time,
            location_name=location_name,
            map_link=map_link,
            website=website,
            terms_condition=terms_condition,
            start_date=start_date,
            end_date=end_date,
            cover_image=cover_image
        )

        result_data = result.get("data")
        if result_data and hasattr(result_data, "_mapping"):
            result_data_dict = dict(result_data)
        elif result_data and isinstance(result_data, dict):
            result_data_dict = result_data
        else:
            result_data_dict = None

        # Send notifications if enabled
        notification_result = None
        if send_notification and result.get("status") == 200 and result_data_dict:
            # Determine notification type
            if announcement_type is not None:
                notification_type = "announcements"  # This will check announcements_alert column
                notification_title = "New Announcement"
                log_module = "Announcement"
            else:
                notification_type = "marketing"  # This will check marketing_alert column
                notification_title = "New Marketing Offer"
                log_module = "Marketing"
            
            # Get all active users with FCM tokens and who have this notification type enabled
            # You can filter by property_id if needed
            users_query = text("""
                SELECT id, fcm_token, email
                FROM user_personal_details 
                WHERE is_active IN (1, 2)
                AND fcm_token IS NOT NULL 
                AND fcm_token != ''
                AND COALESCE({}_alert, 1) = 1
            """.format(notification_type))
            
            # If property_id is provided, filter users by property
            if property_id:
                users_query = text("""
                    SELECT DISTINCT upd.id, upd.fcm_token, upd.email
                    FROM user_personal_details upd
                    INNER JOIN user_properties up ON upd.id = up.user_id
                    WHERE upd.is_active IN (1, 2)
                    AND upd.fcm_token IS NOT NULL 
                    AND upd.fcm_token != ''
                    AND COALESCE(upd.{}_alert, 1) = 1
                    AND up.property_id = :property_id
                """.format(notification_type))
                
                users = db.execute(users_query, {"property_id": property_id}).fetchall()
            else:
                users = db.execute(users_query).fetchall()
            
            notification_results = []
            sent_count = 0
            skipped_count = 0
            
            for user in users:
                # Send notification with preference check
                notif_result = send_push_notification_with_preference(
                    db=db,
                    user_id=user[0],
                    title=notification_title,
                    body=title,  # Using the marketing/announcement title as body
                    notification_type=notification_type,
                    data={
                        "marketing_id": str(result_data_dict.get("id")),
                        "type": notification_type,
                        "title": title,
                        "announcement_type": str(announcement_type) if announcement_type else None,
                        "click_action": "FLUTTER_NOTIFICATION_CLICK"
                    }
                )
                
                notification_results.append({
                    "user_id": user[0],
                    "email": user[2],
                    "status": notif_result.get("status"),
                    "message": notif_result.get("reason") if notif_result.get("status") != "success" else "Sent successfully"
                })
                
                if notif_result.get("status") == "success":
                    sent_count += 1
                elif notif_result.get("status") == "skipped":
                    skipped_count += 1
            
            notification_result = {
                "total_users": len(users),
                "sent_successfully": sent_count,
                "skipped_by_preference": skipped_count,
                "notification_type": notification_type,
                "details": notification_results[:10]  # First 10 results only to avoid large response
            }
            
            # Log notification activity
            log_activity(
                db=db,
                user_id=log_user_id,
                action="Notification Sent",
                module_name=log_module,
                record_id=result_data_dict.get("id"),
                description=f"{notification_title} notification sent to {sent_count} users",
                new_data={
                    "notification_type": notification_type,
                    "title": title,
                    "recipients": sent_count,
                    "skipped": skipped_count
                },
                ip_address=ip_address
            )

        serializable_result = {
            "status": result.get("status"),
            "message": result.get("message"),
            "data": result_data_dict,
            "notifications": notification_result  # Add notification results to response
        }

        log_user_id = creator_id if creator_id is not None else 1  
        
        log_activity(
            db=db,
            user_id=log_user_id,
            action="Create",
            module_name="Marketing",
            record_id=result_data_dict.get("id") if result_data_dict else None,
            description=f"Marketing record created successfully – {title}",
            new_data={
                "payload": {
                    "title": title,
                    "status_id": status_id,
                    "marketing_type_id": marketing_type_id,
                    "announcement_type": announcement_type,
                    "property_id": property_id,
                    "common_area_id": common_area_id,
                    "address": address,
                    "phone": phone,
                    "country_code": country_code,
                    "email": email,
                    "subtext": subtext,
                    "duration_start_date": duration_start_date,
                    "duration_end_date": duration_end_date,
                    "duration_from_time": duration_from_time,
                    "duration_end_time": duration_end_time,
                    "location_name": location_name,
                    "map_link": map_link,
                    "website": website,
                    "terms_condition": terms_condition,
                    "start_date": start_date,
                    "end_date": end_date,
                    "cover_image_filename": cover_image.filename if cover_image else None
                },
                "result": serializable_result,
                "creator_info": {
                    "creator_id": creator_id,
                    "creator_email": creator_email,
                    "creator_name": creator_name,
                    "creator_company_id": creator_company_id
                }
            },
            ip_address=ip_address
        )

        if isinstance(result, dict):
            result["creator_info"] = {
                "id": creator_id,
                "email": creator_email,
                "name": creator_name,
                "company_id": creator_company_id
            }
            result["notifications"] = notification_result  # Add to result

        return result

    except HTTPException as he:
        try:
            log_user_id = creator_id if 'creator_id' in locals() and creator_id is not None else 1
            
            log_activity(
                db=db,
                user_id=log_user_id,
                action="Create Marketing Failed",
                module_name="Marketing",
                description=f"Marketing creation failed: {he.detail}",
                new_data={
                    "payload": {
                        "title": title if 'title' in locals() else None,
                        "status_id": status_id if 'status_id' in locals() else None,
                        "marketing_type_id": marketing_type_id if 'marketing_type_id' in locals() else None,
                        "announcement_type": announcement_type if 'announcement_type' in locals() else None,
                        "property_id": property_id if 'property_id' in locals() else None,
                        "common_area_id": common_area_id if 'common_area_id' in locals() else None,
                        "address": address if 'address' in locals() else None,
                        "phone": phone if 'phone' in locals() else None,
                        "country_code": country_code if 'country_code' in locals() else None,
                        "email": email if 'email' in locals() else None,
                        "subtext": subtext if 'subtext' in locals() else None,
                        "duration_start_date": duration_start_date if 'duration_start_date' in locals() else None,
                        "duration_end_date": duration_end_date if 'duration_end_date' in locals() else None,
                        "duration_from_time": duration_from_time if 'duration_from_time' in locals() else None,
                        "duration_end_time": duration_end_time if 'duration_end_time' in locals() else None,
                        "location_name": location_name if 'location_name' in locals() else None,
                        "map_link": map_link if 'map_link' in locals() else None,
                        "website": website if 'website' in locals() else None,
                        "terms_condition": terms_condition if 'terms_condition' in locals() else None,
                        "start_date": start_date if 'start_date' in locals() else None,
                        "end_date": end_date if 'end_date' in locals() else None,
                        "cover_image_filename": cover_image.filename if 'cover_image' in locals() and cover_image else None
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
        try:
            full_traceback = traceback.format_exc()
            write_to_server_log(f"CRITICAL: Error in create_marketing: {str(e)}\n{full_traceback}")
            
            log_user_id = creator_id if 'creator_id' in locals() and creator_id is not None else 1
            
            log_activity(
                db=db,
                user_id=log_user_id,
                action="Create Marketing Failed",
                module_name="Marketing",
                description=f"Unexpected error while creating marketing record",
                new_data={
                    "payload": {
                        "title": title if 'title' in locals() else "Unknown",
                        "status_id": status_id if 'status_id' in locals() else None,
                        "marketing_type_id": marketing_type_id if 'marketing_type_id' in locals() else None,
                        "announcement_type": announcement_type if 'announcement_type' in locals() else None,
                        "property_id": property_id if 'property_id' in locals() else None,
                        "common_area_id": common_area_id if 'common_area_id' in locals() else None,
                        "address": address if 'address' in locals() else None,
                        "phone": phone if 'phone' in locals() else None,
                        "country_code": country_code if 'country_code' in locals() else None,
                        "email": email if 'email' in locals() else None,
                        "subtext": subtext if 'subtext' in locals() else None,
                        "cover_image_filename": cover_image.filename if 'cover_image' in locals() and cover_image else None
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
        
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred while creating the marketing record.")

@router.put("/update_marketing/{marketing_id}")
async def update_marketing(
    request: Request,
    marketing_id: int,
    updator_email: Optional[str] = Form(None, description="Email of the person updating the marketing record"),
    status_id: Optional[int] = Form(None),
    marketing_type_id: Optional[int] = Form(None),
    announcement_type: Optional[int] = Form(None),
    property_id: Optional[int] = Form(None),
    common_area_id: Optional[int] = Form(None),
    address: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    country_code: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    subtext: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    duration_start_date: Optional[str] = Form(None),
    duration_end_date: Optional[str] = Form(None),
    duration_from_time: Optional[str] = Form(None),
    duration_end_time: Optional[str] = Form(None),
    location_name: Optional[str] = Form(None),
    map_link: Optional[str] = Form(None),
    website: Optional[str] = Form(None),
    terms_condition: Optional[str] = Form(None),
    start_date: Optional[str] = Form(None),
    end_date: Optional[str] = Form(None),
    cover_image: Optional[UploadFile] = Form(None),
    db: Session = Depends(get_db)
):
    try:
        ip_address = request.client.host if request and request.client else "Unknown"
        
        print(f"=== UPDATE MARKETING DEBUG ===")
        print(f"Marketing ID: {marketing_id}")
        print(f"Updator Email: {updator_email}")
        print(f"Title: {title}")
        print(f"Announcement Type: {announcement_type}")
        print(f"Start Date: {start_date}")
        print(f"End Date: {end_date}")
        print(f"Cover Image: {cover_image.filename if cover_image else 'None'}")

        updator_id = None
        updator_name = "Unknown"
        updator_company_id = None

        # Get the existing record before update for tracking changes
        existing_marketing_result = db.execute(
            text("SELECT * FROM marketing WHERE id = :id"),
            {"id": marketing_id}
        ).mappings().first()
        
        print(f"Existing marketing found: {existing_marketing_result is not None}")
        
        if not existing_marketing_result:
            raise HTTPException(status_code=404, detail="Marketing record not found")
        
        existing_marketing = dict(existing_marketing_result)
        print(f"Existing marketing converted to dict, keys: {list(existing_marketing.keys())}")

        if updator_email:
            user_info = db.execute(
                text("SELECT id, name, company_id FROM users WHERE LOWER(email) = LOWER(:email)"),
                {"email": updator_email}
            ).fetchone()

            if user_info:
                updator_id = user_info[0]
                updator_name = user_info[1]
                updator_company_id = user_info[2]
                print(f"Found user: ID={updator_id}, Name={updator_name}")
            else:
                if updator_email.lower() == "bmoadmin@yopmail.com":
                    updator_id = 7
                    updator_name = "BMO Admin"
                    updator_company_id = None
                    print("Using BMO Admin special case")
                else:
                    print(f"User not found for email: {updator_email}")
                    updator_id = 1
                    updator_name = "System Admin"
                    updator_company_id = None

        # Call update service
        result = update_marketing_service(
            db, marketing_id, status_id, marketing_type_id, announcement_type, property_id, common_area_id,
            address, phone, country_code, email, title, subtext, description,
            duration_start_date, duration_end_date, duration_from_time, duration_end_time,
            location_name, map_link, website, terms_condition, start_date, end_date, cover_image
        )

        print(f"Update service result: {result}")

        updated_marketing_result = db.execute(
            text("SELECT * FROM marketing WHERE id = :id"),
            {"id": marketing_id}
        ).mappings().first()
        
        updated_marketing = dict(updated_marketing_result) if updated_marketing_result else {}
        print(f"Updated marketing converted to dict, keys: {list(updated_marketing.keys())}")

        def serialize_for_json(obj):
            if obj is None:
                return None
            if isinstance(obj, (str, int, float, bool)):
                return obj
            if isinstance(obj, datetime):
                return obj.strftime("%Y-%m-%d %H:%M:%S")
            if isinstance(obj, date):
                return obj.strftime("%Y-%m-%d")
            if isinstance(obj, timedelta):
                total_seconds = int(obj.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            if isinstance(obj, (list, tuple)):
                return [serialize_for_json(item) for item in obj]
            if isinstance(obj, dict):
                return {key: serialize_for_json(value) for key, value in obj.items()}
            if hasattr(obj, '_mapping') or hasattr(obj, '_asdict') or hasattr(obj, 'keys'):
                try:
                    return serialize_for_json(dict(obj))
                except:
                    return str(obj)
            return str(obj)

        def deep_serialize(obj):
            """Recursively serialize any object to JSON-compatible format."""
            if obj is None:
                return None
            if isinstance(obj, (str, int, float, bool)):
                return obj
            if isinstance(obj, datetime):
                return obj.strftime("%Y-%m-%d %H:%M:%S")
            if isinstance(obj, date):
                return obj.strftime("%Y-%m-%d")
            if isinstance(obj, timedelta):
                total_seconds = int(obj.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            if isinstance(obj, dict):
                return {key: deep_serialize(value) for key, value in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [deep_serialize(item) for item in obj]
            if hasattr(obj, '_mapping') or hasattr(obj, '_asdict') or hasattr(obj, 'keys'):
                try:
                    return deep_serialize(dict(obj))
                except:
                    return str(obj)
            return str(obj)

        old_data = {}
        new_data = {}
        
        for key, value in existing_marketing.items():
            old_data[key] = serialize_for_json(value)
        
        for key, value in updated_marketing.items():
            new_data[key] = serialize_for_json(value)

        serializable_result = deep_serialize(result)

        log_user_id = updator_id if updator_id is not None else 1
        
        print(f"Logging activity for user_id: {log_user_id}")
        
        payload = {
            "marketing_id": marketing_id,
            "status_id": status_id,
            "marketing_type_id": marketing_type_id,
            "announcement_type": announcement_type,
            "property_id": property_id,
            "common_area_id": common_area_id,
            "address": address,
            "phone": phone,
            "country_code": country_code,
            "email": email,
            "title": title,
            "subtext": subtext,
            "description": description,
            "duration_start_date": duration_start_date,
            "duration_end_date": duration_end_date,
            "duration_from_time": duration_from_time,
            "duration_end_time": duration_end_time,
            "location_name": location_name,
            "map_link": map_link,
            "website": website,
            "terms_condition": terms_condition,
            "start_date": start_date,
            "end_date": end_date,
            "cover_image_filename": cover_image.filename if cover_image else None,
        }
        
        activity_new_data = {
            "payload": deep_serialize(payload),
            "result": serializable_result,
            "updated_record": new_data,
            "updater_info": {
                "updater_id": updator_id,
                "updater_email": updator_email,
                "updater_name": updator_name,
                "updater_company_id": updator_company_id
            }
        }
        
        def check_for_serializable(obj, path=""):
            """Check if object can be JSON serialized."""
            try:
                json.dumps(obj, default=str)
                return True
            except Exception as e:
                print(f"JSON serialization error at {path}: {e}")
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        check_for_serializable(value, f"{path}.{key}")
                elif isinstance(obj, list):
                    for idx, item in enumerate(obj):
                        check_for_serializable(item, f"{path}[{idx}]")
                elif hasattr(obj, '_mapping'):
                    print(f"Found RowMapping at {path}: {type(obj)}")
                return False
        
        print("Checking activity_new_data for JSON serializability...")
        if not check_for_serializable(activity_new_data):
            print("WARNING: activity_new_data contains non-serializable objects!")
        
        log_result = log_activity(
            db=db,
            user_id=log_user_id,
            action="Update",
            module_name="Marketing",
            record_id=marketing_id,
            description=f"Marketing record updated successfully – {title or existing_marketing.get('title', 'No title')}",
            old_data=old_data,
            new_data=activity_new_data,
            ip_address=ip_address
        )
        
        print(f"Activity log result: {log_result}")
        
        verify_log = db.execute(
            text("SELECT * FROM activity_logs WHERE record_id = :record_id AND module_name = 'Marketing' AND action = 'Update' ORDER BY created_at DESC LIMIT 1"),
            {"record_id": marketing_id}
        ).mappings().first()
        
        if verify_log:
            print(f"Activity log verified: ID={verify_log['id']}, Created at={verify_log.get('created_at')}")
        else:
            print("WARNING: No activity log found after update!")

        if isinstance(result, dict):
            result["updater_info"] = {
                "id": updator_id,
                "email": updator_email,
                "name": updator_name,
                "company_id": updator_company_id
            }

        return result

    except HTTPException as he:
        print(f"HTTP Exception in update_marketing: {he.detail}")
        try:
            log_user_id = updator_id if 'updator_id' in locals() and updator_id is not None else 1
            
            error_payload = {
                "marketing_id": marketing_id,
                "title": title if 'title' in locals() else None,
                "status_id": status_id if 'status_id' in locals() else None,
                "marketing_type_id": marketing_type_id if 'marketing_type_id' in locals() else None,
                "announcement_type": announcement_type if 'announcement_type' in locals() else None,
                "property_id": property_id if 'property_id' in locals() else None,
                "common_area_id": common_area_id if 'common_area_id' in locals() else None,
                "address": address if 'address' in locals() else None,
                "phone": phone if 'phone' in locals() else None,
                "country_code": country_code if 'country_code' in locals() else None,
                "email": email if 'email' in locals() else None,
                "cover_image_filename": cover_image.filename if 'cover_image' in locals() and cover_image else None
            }
            
            log_activity(
                db=db,
                user_id=log_user_id,
                action="Update Marketing Failed",
                module_name="Marketing",
                record_id=marketing_id,
                description=f"Marketing update failed: {he.detail}",
                new_data=deep_serialize({
                    "payload": error_payload,
                    "error": he.detail,
                    "updater_info": {
                        "updater_id": updator_id if 'updator_id' in locals() else None,
                        "updater_email": updator_email if 'updator_email' in locals() else None,
                        "updater_name": updator_name if 'updator_name' in locals() else "Unknown",
                        "updater_company_id": updator_company_id if 'updator_company_id' in locals() else None
                    }
                }),
                ip_address=ip_address if 'ip_address' in locals() else "Unknown"
            )
        except Exception as log_error:
            print(f"Failed to log HTTP exception: {log_error}")
            print(f"Traceback: {traceback.format_exc()}")
        raise he

    except Exception as e:
        print(f"Unexpected error in update_marketing: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        
        try:
            full_traceback = traceback.format_exc()
            write_to_server_log(f"CRITICAL: Error in update_marketing: {str(e)}\n{full_traceback}")
            
            log_user_id = updator_id if 'updator_id' in locals() and updator_id is not None else 1
            
            error_payload = {
                "marketing_id": marketing_id,
                "title": title if 'title' in locals() else "Unknown",
                "status_id": status_id if 'status_id' in locals() else None,
                "marketing_type_id": marketing_type_id if 'marketing_type_id' in locals() else None,
                "announcement_type": announcement_type if 'announcement_type' in locals() else None,
                "property_id": property_id if 'property_id' in locals() else None,
                "common_area_id": common_area_id if 'common_area_id' in locals() else None,
                "address": address if 'address' in locals() else None,
                "phone": phone if 'phone' in locals() else None,
                "country_code": country_code if 'country_code' in locals() else None,
                "email": email if 'email' in locals() else None,
                "cover_image_filename": cover_image.filename if 'cover_image' in locals() and cover_image else None
            }
            
            log_activity(
                db=db,
                user_id=log_user_id,
                action="Update Marketing Failed",
                module_name="Marketing",
                record_id=marketing_id,
                description=f"Unexpected error while updating marketing record",
                new_data=deep_serialize({
                    "payload": error_payload,
                    "error": str(e),
                    "traceback": full_traceback,
                    "updater_info": {
                        "updater_id": updator_id if 'updator_id' in locals() else None,
                        "updater_email": updator_email if 'updator_email' in locals() else None,
                        "updater_name": updator_name if 'updator_name' in locals() else "Unknown",
                        "updater_company_id": updator_company_id if 'updator_company_id' in locals() else None
                    }
                }),
                ip_address=ip_address if 'ip_address' in locals() else "Unknown"
            )
        except Exception as log_error:
            print(f"Failed to log error activity: {log_error}")
            print(f"Log error traceback: {traceback.format_exc()}")
        
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred while updating the marketing record: {str(e)}")

# @router.get("/list_marketing", dependencies=[Depends(verify_token)])
# def list_marketing(db: Session = Depends(get_db)):
#     results = list_marketing_service(db)
#     return {
#         "status": 200,
#         "message": "Marketing list retrieved successfully.",
#         "data": results
#     }

@router.get("/list_marketing")
def list_marketing(
    id: Optional[int] = Query(None, description="Get a specific marketing record by ID"),
    status_id: Optional[int] = Query(None),
    marketing_type_id: Optional[str] = Query(None),  
    start_date: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD)"),
    page: int = 1,
    per_page: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    try:
        marketing_type_id_int = int(marketing_type_id) if marketing_type_id and marketing_type_id.strip() else None

        from_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
        to_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None

        results, total_count = list_marketing_service(
            db,
            id=id,
            status_id=status_id,
            marketing_type_id=marketing_type_id_int,
            start_date=from_dt,
            end_date=to_dt,
            page=page,
            record_count=per_page
        )

        last_page = (total_count + per_page - 1) // per_page if total_count else 0

        return {
            "status": 200,
            "message": "Marketing list retrieved successfully." if results else "No records found.",
            "data": results,
            "pagination_details": {
                "page": page,
                "per_page": per_page,
                "total": total_count,
                "last_page": last_page
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list_announcements")
def list_announcements(
    id: Optional[int] = Query(None, description="Get a specific announcement by ID"),
    status_id: Optional[int] = Query(None),
    marketing_type_id: Optional[str] = Query(None),
    announcement_type: Optional[str] = Query(None, description="Filter by announcement type: 1 (general), 2 (building alert), or 'all' for both"),
    start_date: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD)"),
    download: bool = Query(False, description="Set to true to download as Excel or PDF"),
    download_type: Optional[str] = Query('excel', description="Download format: 'excel' or 'pdf'"),
    page: int = 1,
    per_page: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    try:
        marketing_type_id_int = int(marketing_type_id) if marketing_type_id and marketing_type_id.strip() else None
        
        announcement_type_value = None
        if announcement_type and announcement_type.lower() != 'all':
            try:
                announcement_type_value = int(announcement_type)
                if announcement_type_value not in [1, 2]:
                    raise HTTPException(status_code=400, detail="announcement_type must be 1, 2, or 'all'")
            except ValueError:
                raise HTTPException(status_code=400, detail="announcement_type must be 1, 2, or 'all'")

        from_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
        to_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None

        results, total_count = list_announcements_service(
            db,
            id=id,
            status_id=status_id,
            marketing_type_id=marketing_type_id_int,
            announcement_type=announcement_type_value,
            announcement_type_all=(announcement_type and announcement_type.lower() == 'all'),
            start_date=from_dt,
            end_date=to_dt,
            page=page,
            record_count=per_page
        )

        if download:
            if download_type.lower() == 'pdf':
                return generate_pdf_response(results, f"announcements_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
            else: 
                return generate_excel_response(results, f"announcements_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")

        last_page = (total_count + per_page - 1) // per_page if total_count else 0

        return {
            "status": 200,
            "message": "Announcements retrieved successfully." if results else "No records found.",
            "data": results,
            "pagination_details": {
                "page": page,
                "per_page": per_page,
                "total": total_count,
                "last_page": last_page
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/new_list_marketing")
def list_marketing(
    id: Optional[int] = Query(None),
    status_id: Optional[int] = Query(None),
    marketing_type_id: Optional[str] = Query(None), 
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    try:
        marketing_type_id_int = int(marketing_type_id) if marketing_type_id and marketing_type_id.strip() else None

        results, total_count = new_list_marketing_service(
            db,
            id=id,  
            status_id=status_id,
            marketing_type_id=marketing_type_id_int,
            page=page,
            record_count=per_page
        )

        last_page = (total_count + per_page - 1) // per_page

        return {
            "status": 200,
            "message": "Marketing list retrieved successfully.",
            "data": {
                "marketing": results
            },
            "pagination_details": {
                "page": page,
                "per_page": per_page,
                "total": total_count,
                "last_page": last_page
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/listing_marketings")
def list_marketing(
    id: Optional[int] = Query(None),
    status_id: Optional[int] = Query(None),
    marketing_type_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    try:
        marketing_type_id_int = int(marketing_type_id) if marketing_type_id and marketing_type_id.strip() else None

        marketing, total_count = new_listing_marketing_service(
            db,
            id=id,
            status_id=status_id,
            marketing_type_id=marketing_type_id_int,
            page=page,
            record_count=per_page
        )

        last_page = (total_count + per_page - 1) // per_page

        return {
            "status": 200,
            "message": "Marketing retrieved successfully.",
            "data": {
                "marketing": marketing
            },
            "pagination_details": {
                "page": page,
                "per_page": per_page,
                "total": total_count,
                "last_page": last_page
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/listing_marketing_search")
def list_marketing(
    id: Optional[int] = Query(None),
    status_id: Optional[int] = Query(None),
    marketing_type_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Search keyword"),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    request: Request = None
):
    try:
        marketing_type_id_int = int(marketing_type_id) if marketing_type_id and marketing_type_id.strip() else None

        results, total_count = list_marketing_search(
            db,
            id=id,
            status_id=status_id,
            marketing_type_id=marketing_type_id_int,
            search=search,
            page=page,
            record_count=per_page
        )

        last_page = (total_count + per_page - 1) // per_page if total_count else 1

        query_params = dict(request.query_params)
        query_params.pop("page", None)
        extra_params = "&".join([f"{k}={v}" for k, v in query_params.items()]) if query_params else ""

        def make_url(p):
            if not p:
                return None
            return f"{str(request.url).split('?')[0]}?page={p}" + (f"&{extra_params}" if extra_params else "")

        from_record = (page - 1) * per_page + 1 if total_count > 0 else None
        to_record = min(page * per_page, total_count) if total_count > 0 else None

        links = [{"url": make_url(page - 1), "label": "pagination.previous", "active": False}]
        for p in range(1, last_page + 1):
            links.append({
                "url": make_url(p),
                "label": str(p),
                "active": (p == page)
            })
        links.append({"url": make_url(page + 1), "label": "pagination.next", "active": False})

        return {
            "status": 200,
            "message": "Marketing list retrieved successfully.",
            "data": {
                "marketing": results
            },
            "pagination_details": {
                "current_page": page,
                "first_page_url": make_url(1),
                "from": from_record,
                "last_page": last_page,
                "last_page_url": make_url(last_page),
                "links": links,
                "next_page_url": make_url(page + 1) if page < last_page else None,
                "path": str(request.url).split("?")[0],
                "per_page": per_page,
                "prev_page_url": make_url(page - 1) if page > 1 else None,
                "to": to_record,
                "total": total_count
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete_marketing/{marketing_id}")
def delete_marketing(marketing_id: int, db: Session = Depends(get_db)):
    return delete_marketing_service(db, marketing_id)



@router.put("/update_announcement_status/{marketing_id}")
async def update_announcement_status(
    request: Request,
    marketing_id: int,
    updator_email: Optional[str] = Query(None, description="Email of the person updating the announcement status"),
    payload: dict = Body(..., description="JSON payload with is_active and optional status_id fields"),
    db: Session = Depends(get_db)
):
    """Update the active status and/or status_id of an announcement
    
    Request format:
    PUT /update_announcement_status/68?updator_email=admin@yopmail.com
    Content-Type: application/json
    
    {
        "is_active": true,
        "status_id": 1  // Optional
    }
    """
    try:
        ip_address = request.client.host if request and request.client else "Unknown"
        
        is_active = payload.get("is_active")
        status_id = payload.get("status_id")  
        
        if is_active is None:
            raise HTTPException(
                status_code=400, 
                detail="Missing required field: is_active. Please provide true or false in the JSON payload."
            )
        
        if isinstance(is_active, str):
            is_active = is_active.lower() in ['true', '1', 'yes']
        elif not isinstance(is_active, bool):
            raise HTTPException(
                status_code=400, 
                detail="is_active must be a boolean value (true/false)"
            )
        
        if status_id is not None:
            if isinstance(status_id, str):
                try:
                    status_id = int(status_id)
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail="status_id must be an integer value"
                    )
            elif not isinstance(status_id, int):
                raise HTTPException(
                    status_code=400,
                    detail="status_id must be an integer value"
                )
            
            status_exists = db.execute(
                text("SELECT id FROM marketing_status WHERE id = :status_id"),
                {"status_id": status_id}
            ).fetchone()
            
            if not status_exists:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status_id: {status_id}. Status does not exist."
                )
        
        print(f"=== UPDATE ANNOUNCEMENT STATUS DEBUG ===")
        print(f"Marketing ID: {marketing_id}")
        print(f"Is Active: {is_active}")
        print(f"Status ID: {status_id}")
        print(f"Updator Email: {updator_email}")

        updator_id = None
        updator_name = "Unknown"
        updator_company_id = None

        existing_marketing_result = db.execute(
            text("SELECT * FROM marketing WHERE id = :id"),
            {"id": marketing_id}
        ).mappings().first()
        
        if not existing_marketing_result:
            raise HTTPException(status_code=404, detail="Marketing record not found")
        
        if existing_marketing_result.get("announcement_type") is None:
            raise HTTPException(
                status_code=400, 
                detail="This record is not an announcement. Only announcements can have active/inactive status."
            )
        
        existing_marketing = dict(existing_marketing_result)

        if updator_email:
            user_info = db.execute(
                text("SELECT id, name, company_id FROM users WHERE LOWER(email) = LOWER(:email)"),
                {"email": updator_email}
            ).fetchone()

            if user_info:
                updator_id = user_info[0]
                updator_name = user_info[1]
                updator_company_id = user_info[2]
                print(f"Found user: ID={updator_id}, Name={updator_name}")
            else:
                if updator_email.lower() == "bmoadmin@yopmail.com":
                    updator_id = 7
                    updator_name = "BMO Admin"
                    updator_company_id = None
                    print("Using BMO Admin special case")
                else:
                    print(f"User not found for email: {updator_email}")
                    updator_id = 1
                    updator_name = "System Admin"
                    updator_company_id = None

        result = update_announcement_active_status_service(
            db=db,
            marketing_id=marketing_id,
            is_announcement_active=is_active,
            status_id=status_id 
        )

        updated_marketing_result = db.execute(
            text("SELECT * FROM marketing WHERE id = :id"),
            {"id": marketing_id}
        ).mappings().first()
        
        updated_marketing = dict(updated_marketing_result) if updated_marketing_result else {}

        def serialize_for_json(obj):
            if obj is None:
                return None
            if isinstance(obj, (str, int, float, bool)):
                return obj
            if isinstance(obj, datetime):
                return obj.strftime("%Y-%m-%d %H:%M:%S")
            if isinstance(obj, date):
                return obj.strftime("%Y-%m-%d")
            if isinstance(obj, timedelta):
                total_seconds = int(obj.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            return str(obj)

        def deep_serialize(obj):
            if obj is None:
                return None
            if isinstance(obj, (str, int, float, bool)):
                return obj
            if isinstance(obj, datetime):
                return obj.strftime("%Y-%m-%d %H:%M:%S")
            if isinstance(obj, date):
                return obj.strftime("%Y-%m-%d")
            if isinstance(obj, timedelta):
                total_seconds = int(obj.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            if isinstance(obj, dict):
                return {key: deep_serialize(value) for key, value in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [deep_serialize(item) for item in obj]
            return str(obj)

        old_data = {
            "id": marketing_id,
            "title": existing_marketing.get("title"),
            "is_announcement_active": existing_marketing.get("is_announcement_active", False),
            "status_id": existing_marketing.get("status_id")
        }
        
        new_data = {
            "id": marketing_id,
            "title": updated_marketing.get("title"),
            "is_announcement_active": is_active,
            "status_id": status_id if status_id is not None else updated_marketing.get("status_id")
        }

        log_user_id = updator_id if updator_id is not None else 1
        
        activity_new_data = {
            "payload": {
                "marketing_id": marketing_id,
                "is_active": is_active,
                "status_id": status_id,
                "title": existing_marketing.get("title")
            },
            "result": result,
            "updated_record": updated_marketing,
            "updater_info": {
                "updater_id": updator_id,
                "updater_email": updator_email,
                "updater_name": updator_name,
                "updater_company_id": updator_company_id
            }
        }

        log_activity(
            db=db,
            user_id=log_user_id,
            action="Update Announcement Status",
            module_name="Marketing",
            record_id=marketing_id,
            description=f"Announcement '{existing_marketing.get('title')}' {'activated' if is_active else 'deactivated'}" + (f" and status updated to {status_id}" if status_id else ""),
            old_data=deep_serialize(old_data),
            new_data=deep_serialize(activity_new_data),
            ip_address=ip_address
        )

        # Add updater info to the result
        if isinstance(result, dict):
            result["updater_info"] = {
                "id": updator_id,
                "email": updator_email,
                "name": updator_name,
                "company_id": updator_company_id
            }

        return result

    except HTTPException as he:
        print(f"HTTP Exception in update_announcement_status: {he.detail}")
        try:
            log_user_id = updator_id if 'updator_id' in locals() and updator_id is not None else 1
            
            log_activity(
                db=db,
                user_id=log_user_id,
                action="Update Announcement Status Failed",
                module_name="Marketing",
                record_id=marketing_id,
                description=f"Failed to update announcement: {he.detail}",
                new_data=deep_serialize({
                    "payload": {
                        "marketing_id": marketing_id,
                        "is_active": is_active if 'is_active' in locals() else None,
                        "status_id": status_id if 'status_id' in locals() else None
                    },
                    "error": he.detail,
                    "updater_info": {
                        "updater_id": updator_id if 'updator_id' in locals() else None,
                        "updater_email": updator_email if 'updator_email' in locals() else None,
                        "updater_name": updator_name if 'updator_name' in locals() else "Unknown"
                    }
                }),
                ip_address=ip_address if 'ip_address' in locals() else "Unknown"
            )
        except Exception as log_error:
            print(f"Failed to log error: {log_error}")
        raise he

    except Exception as e:
        print(f"Unexpected error in update_announcement_status: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"An unexpected error occurred while updating announcement status: {str(e)}"
        )