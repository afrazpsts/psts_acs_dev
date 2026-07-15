from fastapi import APIRouter, HTTPException, Depends, Query, Request
from sqlalchemy.orm import Session
from DB.db import get_db
from .service import (
    create_user_service,
    get_user_by_id_service,
    get_user_by_email_service,
    send_otp_service,
    set_user_password,
    update_user_service,
    delete_user_service,
    verify_user_otp,
    list_users_service ,
    update_user_status_service
)
import random
import string
from datetime import datetime, timedelta
from common.logger import log as write_to_server_log
import traceback
from sqlalchemy import text
from .models import OTPVerifyRequest, SetPasswordRequest
from typing import Optional
from activity_logs.service import log_activity

router = APIRouter(prefix="/users", tags=["Users"])

def _resolve_actor_from_email(db: Session, actor_email: Optional[str]):
    actor_id = None
    actor_name = "Unknown"
    actor_company_id = None

    if actor_email:
        actor_info = db.execute(
            text("SELECT id, name, company_id FROM users WHERE LOWER(email) = LOWER(:email)"),
            {"email": actor_email},
        ).fetchone()

        if actor_info:
            actor_id = actor_info[0]
            actor_name = actor_info[1]
            actor_company_id = actor_info[2]
        else:
            if actor_email.lower() == "bmoadmin@yopmail.com":
                actor_id = 7
                actor_name = "BMO Admin"
                actor_company_id = None
            else:
                actor_id = 1
                actor_name = "System Admin"
                actor_company_id = None

    return actor_id, actor_name, actor_company_id

@router.post("/create_user")
async def create_user(
    request: Request,
    payload: dict,
    creator_email: Optional[str] = Query(None, description="Email of the person creating the user"),
    db: Session = Depends(get_db)
):
    try:
        ip_address = request.client.host if request and request.client else "Unknown"
        
        name = payload.get("name")
        email = payload.get("email")
        phone = payload.get("phone")
        password = payload.get("password")
        company_id = payload.get("company_id")
        role_id = payload.get("role_id")
        created_by = payload.get("created_by")
        sub_user_role = payload.get("sub_user_role")
        is_user_active = payload.get("is_user_active", "true")
        on_board_date = payload.get("on_board_date")
        off_board_date = payload.get("off_board_date")
        menu_permissions = payload.get("menu_permissions")

        write_to_server_log("API: Entering create_user endpoint")

        if not name:
            raise HTTPException(status_code=400, detail="Name is required")

        creator_name = "Unknown"
        creator_company_id = None
        
        if creator_email:
            if creator_email.lower() == "bmoadmin@yopmail.com":
                creator_name = "BMO Admin"
                creator_company_id = None
            else:
                creator_info = db.execute(
                    text("SELECT id, name, company_id FROM users WHERE email = :email"),  
                    {"email": creator_email}
                ).fetchone()
                
                if creator_info:
                    created_by = creator_info[0]  
                    creator_name = creator_info[1]
                    creator_company_id = creator_info[2]
                else:
                    creator_name = creator_email.split('@')[0]
        
        elif created_by:
            creator_info = db.execute(
                text("SELECT email, name, company_id FROM users WHERE id = :user_id"),  
                {"user_id": created_by}
            ).fetchone()
            
            if creator_info:
                creator_email = creator_info[0]
                creator_name = creator_info[1]
                creator_company_id = creator_info[2]
            else:
                if str(created_by) == "7":
                    creator_email = "bmoadmin@yopmail.com"
                    creator_name = "BMO Admin"
                    creator_company_id = None

        otp = f"{random.randint(100000, 999999)}"
        otp_expiry = (datetime.now() + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
        is_verified = payload.get("is_verified", False)

        result = create_user_service(
            name=name,
            email=email,
            phone=phone,
            password=password,
            company_id=company_id,
            role_id=role_id,
            is_verified=is_verified,
            otp=otp,
            otp_expiry=otp_expiry,
            created_by=created_by,
            sub_user_role=sub_user_role,
            is_user_active=is_user_active,
            on_board_date=on_board_date,
            off_board_date=off_board_date,
            db=db
        )

        permissions_count = 0
        permissions_type = "none"
        
        if menu_permissions is not None:
            if isinstance(menu_permissions, bool) and menu_permissions is True:
                permissions_type = "all"
                permissions_count = "all"
            elif isinstance(menu_permissions, list):
                permissions_type = "specific"
                permissions_count = len(menu_permissions)

        log_activity(
            db=db,
            user_id=created_by,
            action="Create",
            module_name="Users",
            record_id=result.get("user_id"),
            description=f"User account created successfully – {name} ({email})",
            new_data={
                "payload": {
                    "name": name,
                    "email": email,
                    "phone": phone,
                    "company_id": company_id,
                    "role_id": role_id,
                    "sub_user_role": sub_user_role,
                    "is_user_active": is_user_active,
                    "on_board_date": on_board_date,
                    "off_board_date": off_board_date,
                    "menu_permissions": {
                        "type": permissions_type,
                        "count": permissions_count
                    }
                },
                "result": {
                    "user_id": result.get("user_id"),
                    "status": "created"
                },
                "creator_info": {
                    "creator_id": created_by,
                    "creator_email": creator_email,
                    "creator_name": creator_name,
                    "creator_company_id": creator_company_id
                }
            },
            ip_address=ip_address
        )

        if menu_permissions is not None and role_id:
            from menu import service as menu_service
            
            if isinstance(menu_permissions, bool) and menu_permissions is True:
                all_menus_result = db.execute(text("SELECT id FROM menu_list"))
                all_menu_ids = [row[0] for row in all_menus_result.fetchall()]
                
                menu_service.set_role_menu_permission(
                    role_id=int(role_id),
                    menu_ids=all_menu_ids,
                    enabled=1,
                    db=db
                )
                write_to_server_log(f"All menu permissions enabled for role {role_id}: {len(all_menu_ids)} menus")
                
                log_activity(
                    db=db,
                    user_id=created_by,
                    action="Assign All Menu Permissions",
                    module_name="Users",
                    record_id=result.get("user_id"),
                    description=f"Assigned ALL menu permissions to user {name}",
                    new_data={
                        "user_id": result.get("user_id"),
                        "user_name": name,
                        "role_id": role_id,
                        "menu_permissions": "ALL",
                        "permissions_count": len(all_menu_ids),
                        "creator_info": {
                            "creator_id": created_by,
                            "creator_email": creator_email,
                            "creator_name": creator_name
                        }
                    },
                    ip_address=ip_address
                )
                
                permissions_set_display = "all"
                
            elif isinstance(menu_permissions, list) and len(menu_permissions) > 0:
                menu_service.set_role_menu_permission(
                    role_id=int(role_id),
                    menu_ids=menu_permissions,
                    enabled=1,
                    db=db
                )
                write_to_server_log(f"Menu permissions set for role {role_id}: {len(menu_permissions)} menus")
                
                log_activity(
                    db=db,
                    user_id=created_by,
                    action="Assign Menu Permissions",
                    module_name="Users",
                    record_id=result.get("user_id"),
                    description=f"Assigned {len(menu_permissions)} menu permissions to user {name}",
                    new_data={
                        "user_id": result.get("user_id"),
                        "user_name": name,
                        "role_id": role_id,
                        "menu_permissions": menu_permissions,
                        "permissions_count": len(menu_permissions),
                        "creator_info": {
                            "creator_id": created_by,
                            "creator_email": creator_email,
                            "creator_name": creator_name
                        }
                    },
                    ip_address=ip_address
                )
                
                permissions_set_display = len(menu_permissions)
            else:
                permissions_set_display = 0
        else:
            permissions_set_display = 0

        response_data = {
            "message": "User created successfully",
            "data": {
                "user": result,
                "permissions_set": permissions_set_display
            },
            "status": 201,
            "creator_info": {
                "id": created_by,
                "email": creator_email,
                "name": creator_name,
                "company_id": creator_company_id
            }
        }

        return response_data

    except HTTPException as he:
        try:
            log_activity(
                db=db,
                user_id=created_by if 'created_by' in locals() else None,
                action="Create User Failed",
                module_name="Users",
                description=f"User creation failed: {he.detail}",
                new_data={
                    "payload": payload,
                    "error": he.detail,
                    "creator_info": {
                        "creator_id": created_by if 'created_by' in locals() else None,
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
        error_message = str(e)
        
        if "User with this email already exists" in error_message:
            status_code = 400
        else:
            status_code = 500
        
        try:
            full_traceback = traceback.format_exc()
            write_to_server_log(f"Error in create_user: {error_message}\n{full_traceback}")
            
            log_activity(
                db=db,
                user_id=created_by if 'created_by' in locals() else None,
                action="Create User Failed",
                module_name="Users",
                description=f"Error while creating user: {error_message}",
                new_data={
                    "payload": payload,
                    "error": error_message,
                    "traceback": full_traceback,
                    "creator_info": {
                        "creator_id": created_by if 'created_by' in locals() else None,
                        "creator_email": creator_email if 'creator_email' in locals() else None,
                        "creator_name": creator_name if 'creator_name' in locals() else "Unknown",
                        "creator_company_id": creator_company_id if 'creator_company_id' in locals() else None
                    }
                },
                ip_address=ip_address if 'ip_address' in locals() else "Unknown"
            )
        except Exception as log_error:
            print(f"Failed to log error activity: {log_error}")
        
        raise HTTPException(status_code=status_code, detail=error_message)

@router.post("/sending_otp")
def send_otp(payload: dict, db: Session = Depends(get_db)):
    """
    Send OTP to user's email with validations:
    - Check if email exists
    - Check if account already verified
    - Check off-board date expiry
    - Check on-board date start
    """
    try:
        email = payload.get("email")
        
        if not email:
            raise HTTPException(status_code=400, detail="Email is required")
        
        write_to_server_log(f"API: Sending OTP to email: {email}")
        
        quick_check = db.execute(
            text("SELECT email FROM users WHERE email = :email"),
            {"email": email}
        ).first()
        
        if not quick_check:
            write_to_server_log(f"Email not found in quick check: {email}")
            raise HTTPException(
                status_code=404, 
                detail="Email does not exist in our records. Please check the email or sign up first."
            )
        
        result = send_otp_service(email, db)
        
        return {
            "message": "OTP sent successfully",
            "data": result,
            "status": 200
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        write_to_server_log(f"Error in send_otp: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error sending OTP: {str(e)}")

@router.post("/verify_otp")
def verify_otp(payload: OTPVerifyRequest, db: Session = Depends(get_db)):
    """
    Verify OTP for a user and mark email as verified.
    Checks:
    - Account exists
    - Password already set (prevents OTP verification if password exists)
    - OTP expiry
    - OTP match
    """
    try:
        write_to_server_log(f"API: Verifying OTP for email: {payload.email}")
        
        response = verify_user_otp(db, payload.email, payload.otp)
        return response
        
    except HTTPException as he:
        raise he
    except Exception as e:
        write_to_server_log(f"Error in verify_otp: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    
@router.post("/set_password")
def set_password(payload: SetPasswordRequest, db: Session = Depends(get_db)):
    """
    Set new password for verified user.
    """
    try:
        response = set_user_password(db, payload.email, payload.password)
        return response
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/get_user/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    try:
        result = get_user_by_id_service(user_id, db)
        
        if not result:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "message": "User retrieved successfully",
            "data": result,
            "status": 200
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error retrieving user: {str(e)}")

@router.get("/get_user_by_email")
def get_user_by_email(email: str, db: Session = Depends(get_db)):
    try:
        if not email:
            raise HTTPException(status_code=400, detail="Email is required")
            
        result = get_user_by_email_service(email, db)
        
        if not result:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "message": "User retrieved successfully",
            "data": result,
            "status": 200
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error retrieving user: {str(e)}")

def _mask_password_in_payload(payload: dict) -> dict:
    if not payload:
        return payload
    out = dict(payload)
    if "password" in out:
        out["password"] = "[redacted]"
    return out


@router.put("/update_user/{user_id}")
async def update_user(
    request: Request,
    user_id: int,
    payload: dict,
    updator_email: Optional[str] = Query(None, description="Email of the person updating the user"),
    db: Session = Depends(get_db),
):
    ip_address = request.client.host if request and request.client else "Unknown"
    updator_id, updator_name, updator_company_id = _resolve_actor_from_email(db, updator_email)

    try:
        old_user = get_user_by_id_service(user_id, db)
        if not old_user:
            raise HTTPException(status_code=404, detail="User not found")

        payload_for_update = dict(payload)
        menu_permissions = payload_for_update.pop("menu_permissions", None)

        result = update_user_service(user_id, payload_for_update, db)

        name = result.get("name") or old_user.get("name")
        email = result.get("email") or old_user.get("email")
        effective_role_id = result.get("role_id")
        if effective_role_id is None:
            effective_role_id = old_user.get("role_id")
        try:
            effective_role_id_int = int(effective_role_id) if effective_role_id is not None else None
        except (TypeError, ValueError):
            effective_role_id_int = None

        permissions_count = 0
        permissions_type = "none"
        if menu_permissions is not None:
            if isinstance(menu_permissions, bool) and menu_permissions is True:
                permissions_type = "all"
                permissions_count = "all"
            elif isinstance(menu_permissions, list):
                permissions_type = "specific"
                permissions_count = len(menu_permissions)

        log_user_id = updator_id if updator_id is not None else 1
        payload_log = _mask_password_in_payload(payload_for_update)
        if menu_permissions is not None:
            payload_log = {
                **payload_log,
                "menu_permissions": {
                    "type": permissions_type,
                    "count": permissions_count,
                },
            }

        log_activity(
            db=db,
            user_id=log_user_id,
            action="Update",
            module_name="Users",
            record_id=user_id,
            description=f"User updated successfully – {name} ({email})",
            old_data={"user": old_user},
            new_data={
                "payload": payload_log,
                "result": {"user_id": user_id, "status": "updated"},
                "updator_info": {
                    "updator_id": updator_id,
                    "updator_email": updator_email,
                    "updator_name": updator_name,
                    "updator_company_id": updator_company_id,
                },
            },
            ip_address=ip_address,
        )

        permissions_set_display = 0
        if menu_permissions is not None and effective_role_id_int:
            from menu import service as menu_service

            if isinstance(menu_permissions, bool) and menu_permissions is True:
                all_menus_result = db.execute(text("SELECT id FROM menu_list"))
                all_menu_ids = [row[0] for row in all_menus_result.fetchall()]

                menu_service.set_role_menu_permission(
                    role_id=effective_role_id_int,
                    menu_ids=all_menu_ids,
                    enabled=1,
                    db=db,
                )
                write_to_server_log(
                    f"Update user: all menu permissions enabled for role {effective_role_id_int}: {len(all_menu_ids)} menus"
                )

                log_activity(
                    db=db,
                    user_id=log_user_id,
                    action="Assign All Menu Permissions",
                    module_name="Users",
                    record_id=user_id,
                    description=f"Assigned ALL menu permissions to user {name} (on update)",
                    new_data={
                        "user_id": user_id,
                        "user_name": name,
                        "role_id": effective_role_id_int,
                        "menu_permissions": "ALL",
                        "permissions_count": len(all_menu_ids),
                        "updator_info": {
                            "updator_id": updator_id,
                            "updator_email": updator_email,
                            "updator_name": updator_name,
                        },
                    },
                    ip_address=ip_address,
                )
                permissions_set_display = "all"

            elif isinstance(menu_permissions, list) and len(menu_permissions) > 0:
                menu_service.set_role_menu_permission(
                    role_id=effective_role_id_int,
                    menu_ids=menu_permissions,
                    enabled=1,
                    db=db,
                )
                write_to_server_log(
                    f"Update user: menu permissions set for role {effective_role_id_int}: {len(menu_permissions)} menus"
                )

                log_activity(
                    db=db,
                    user_id=log_user_id,
                    action="Assign Menu Permissions",
                    module_name="Users",
                    record_id=user_id,
                    description=f"Assigned {len(menu_permissions)} menu permissions to user {name} (on update)",
                    new_data={
                        "user_id": user_id,
                        "user_name": name,
                        "role_id": effective_role_id_int,
                        "menu_permissions": menu_permissions,
                        "permissions_count": len(menu_permissions),
                        "updator_info": {
                            "updator_id": updator_id,
                            "updator_email": updator_email,
                            "updator_name": updator_name,
                        },
                    },
                    ip_address=ip_address,
                )
                permissions_set_display = len(menu_permissions)
            else:
                permissions_set_display = 0
        else:
            if menu_permissions is not None and not effective_role_id_int:
                write_to_server_log(
                    f"Update user: menu_permissions skipped — no role_id for user {user_id}"
                )

        response_data = {
            "message": "User updated successfully",
            "data": {
                "user": result,
                "permissions_set": permissions_set_display,
            },
            "status": 200,
            "updator_info": {
                "id": updator_id,
                "email": updator_email,
                "name": updator_name,
                "company_id": updator_company_id,
            },
        }
        return response_data

    except HTTPException as he:
        try:
            log_activity(
                db=db,
                user_id=updator_id if updator_id is not None else None,
                action="Update User Failed",
                module_name="Users",
                record_id=user_id,
                description=f"User update failed: {he.detail}",
                new_data={
                    "payload": _mask_password_in_payload(payload),
                    "error": he.detail,
                    "updator_info": {
                        "updator_id": updator_id,
                        "updator_email": updator_email,
                        "updator_name": updator_name,
                        "updator_company_id": updator_company_id,
                    },
                },
                ip_address=ip_address,
            )
        except Exception as log_error:
            print(f"Failed to log HTTP exception (update_user): {log_error}")
        raise he

    except Exception as e:
        error_message = str(e)
        if "Email already exists" in error_message:
            status_code = 400
        else:
            status_code = 500
        try:
            full_traceback = traceback.format_exc()
            write_to_server_log(f"Error in update_user: {error_message}\n{full_traceback}")
            log_activity(
                db=db,
                user_id=updator_id if updator_id is not None else None,
                action="Update User Failed",
                module_name="Users",
                record_id=user_id,
                description=f"Error while updating user: {error_message}",
                new_data={
                    "payload": _mask_password_in_payload(payload),
                    "error": error_message,
                    "traceback": full_traceback,
                    "updator_info": {
                        "updator_id": updator_id,
                        "updator_email": updator_email,
                        "updator_name": updator_name,
                        "updator_company_id": updator_company_id,
                    },
                },
                ip_address=ip_address,
            )
        except Exception as log_error:
            print(f"Failed to log error activity (update_user): {log_error}")
        raise HTTPException(status_code=status_code, detail=error_message)

@router.delete("/delete_user/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    try:
        existing_user = get_user_by_id_service(user_id, db)
        if not existing_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        result = delete_user_service(user_id, db)
        
        return {
            "message": "User deleted successfully",
            "data": result,
            "status": 200
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error deleting user: {str(e)}")

@router.get("/list_users")
async def list_users(
    request: Request,
    user_id: Optional[str] = Query(None, description="Filter by specific user ID"),
    searchdata: Optional[str] = Query(None, description="Search in name, email, phone, role, company"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page"),
    from_date: Optional[str] = Query(None, description="Filter from this date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="Filter to this date (YYYY-MM-DD)"),
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    role_id: Optional[int] = Query(None, description="Filter by role ID"),
    is_user_active: Optional[str] = Query(None, description="Filter by active status (true/false)"),
    is_verified: Optional[int] = Query(None, description="Filter by verification status (0/1)"),
    include_menu_permissions: bool = Query(True, description="Include menu permissions for each user"),
    exclude_super_admin: bool = Query(True, description="Exclude Super Admin (role_id=1) from results"),
    db: Session = Depends(get_db)
):
    """
    List users with pagination and filtering options.
    If user_id is provided, returns only that specific user.
    Includes menu permissions for each user based on their role from role_menu_permission table.
    """
    try:
        ip_address = request.client.host if request and request.client else "Unknown"
        
        if is_user_active == "null" or is_user_active == "None":
            is_user_active = None
        
        # Handle user_id properly - convert string to int or None
        parsed_user_id = None
        if user_id is not None and user_id != "" and user_id.lower() != "null" and user_id.lower() != "none":
            try:
                parsed_user_id = int(user_id)
            except (ValueError, TypeError):
                parsed_user_id = None
        
        write_to_server_log(f"API: Listing users with filters - user_id: {parsed_user_id}, search: {searchdata}, page: {page}, per_page: {per_page}")
        
        result = list_users_service(
            db=db,
            user_id=parsed_user_id,
            searchdata=searchdata,
            from_date=from_date,
            to_date=to_date,
            company_id=company_id,
            role_id=role_id,
            is_user_active=is_user_active,
            is_verified=is_verified,
            page=page,
            per_page=per_page,
            exclude_super_admin=exclude_super_admin
        )
        
        if not include_menu_permissions:
            for user in result['users']:
                user.pop('menu_permissions', None)
        
        last_page = result['total_pages']
        
        log_activity(
            db=db,
            user_id=None,
            action="List Users",
            module_name="Users",
            description=f"Retrieved list of users with filters - Page: {page}, Total: {result['total']}",
            new_data={
                "filters": {
                    "user_id": parsed_user_id,
                    "searchdata": searchdata,
                    "from_date": from_date,
                    "to_date": to_date,
                    "company_id": company_id,
                    "role_id": role_id,
                    "is_user_active": is_user_active,
                    "is_verified": is_verified
                },
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": result['total'],
                    "last_page": last_page
                }
            },
            ip_address=ip_address
        )
        
        return {
            "message": "Users retrieved successfully",
            "data": result['users'],
            "pagination_details": {
                "page": result['page'],
                "per_page": result['per_page'],
                "total": result['total'],
                "last_page": last_page
            },
            "filters_applied": {
                "user_id": parsed_user_id,
                "searchdata": searchdata,
                "from_date": from_date,
                "to_date": to_date,
                "company_id": company_id,
                "role_id": role_id,
                "is_user_active": is_user_active,
                "is_verified": is_verified,
                "exclude_super_admin": exclude_super_admin
            },
            "status": 200
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        error_message = str(e)
        write_to_server_log(f"Error in list_users: {error_message}")
        import traceback
        write_to_server_log(f"Traceback: {traceback.format_exc()}")
        
        try:
            log_activity(
                db=db,
                user_id=None,
                action="List Users Failed",
                module_name="Users",
                description=f"Error while listing users: {error_message}",
                new_data={
                    "error": error_message,
                    "filters": {
                        "user_id": parsed_user_id if 'parsed_user_id' in locals() else None,
                        "searchdata": searchdata,
                        "from_date": from_date,
                        "to_date": to_date,
                        "company_id": company_id,
                        "role_id": role_id,
                        "is_user_active": is_user_active,
                        "is_verified": is_verified
                    }
                },
                ip_address=ip_address if 'ip_address' in locals() else "Unknown"
            )
        except:
            pass
        
        raise HTTPException(status_code=500, detail=f"Error retrieving users: {error_message}")
    
@router.put("/update_user_status/{user_id}")
def update_user_status(
    request: Request,
    user_id: int,
    payload: dict,
    updator_email: Optional[str] = Query(None, description="Email of the person updating the user status"),
    db: Session = Depends(get_db),
):
    """
    Update user active status (is_user_active)
    Accepts true/false or 1/0
    """
    try:
        ip_address = request.client.host if request and request.client else "Unknown"
        updator_id, updator_name, updator_company_id = _resolve_actor_from_email(db, updator_email)

        old_user = get_user_by_id_service(user_id, db)
        if not old_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        is_user_active = payload.get("is_user_active")
        
        if is_user_active is None:
            raise HTTPException(status_code=400, detail="is_user_active field is required")
        
        if isinstance(is_user_active, bool):
            is_user_active_str = "true" if is_user_active else "false"
        elif isinstance(is_user_active, int):
            if is_user_active not in [0, 1]:
                raise HTTPException(status_code=400, detail="is_user_active must be 0, 1, true, or false")
            is_user_active_str = "true" if is_user_active == 1 else "false"
        elif isinstance(is_user_active, str):
            if is_user_active.lower() in ['true', '1']:
                is_user_active_str = "true"
            elif is_user_active.lower() in ['false', '0']:
                is_user_active_str = "false"
            else:
                raise HTTPException(status_code=400, detail="is_user_active must be true/false or 1/0")
        else:
            raise HTTPException(status_code=400, detail="is_user_active must be a boolean, integer, or string")
        
        result = update_user_status_service(user_id, is_user_active_str, db)
        
        if not result:
            raise HTTPException(status_code=404, detail="User not found")
        
        log_user_id = updator_id if updator_id is not None else 1
        status_text = "activated" if is_user_active_str == "true" else "deactivated"
        
        log_activity(
            db=db,
            user_id=log_user_id,
            action="Update Status",
            module_name="Users",
            record_id=user_id,
            description=f"User {status_text} successfully – {old_user.get('name')} ({old_user.get('email')})",
            old_data={"user": old_user, "is_user_active": old_user.get("is_user_active")},
            new_data={
                "payload": {"user_id": user_id, "is_user_active": is_user_active},
                "result": {
                    "status": 200, 
                    "message": f"User {status_text} successfully", 
                    "data": result
                },
                "creator_info": {
                    "creator_id": updator_id,
                    "creator_email": updator_email,
                    "creator_name": updator_name,
                    "creator_company_id": updator_company_id,
                },
            },
            ip_address=ip_address,
        )
        
        return {
            "message": f"User {status_text} successfully",
            "data": result,
            "status": 200,
            "creator_info": {
                "id": updator_id,
                "email": updator_email,
                "name": updator_name,
                "company_id": updator_company_id,
            },
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        error_message = str(e)
        write_to_server_log(f"Error in update_user_status: {error_message}")
        import traceback
        write_to_server_log(f"Traceback: {traceback.format_exc()}")
        
        try:
            log_activity(
                db=db,
                user_id=updator_id if 'updator_id' in locals() else None,
                action="Update User Status Failed",
                module_name="Users",
                description=f"Error while updating user status: {error_message}",
                new_data={
                    "user_id": user_id,
                    "payload": payload,
                    "error": error_message,
                    "creator_info": {
                        "creator_id": updator_id if 'updator_id' in locals() else None,
                        "creator_email": updator_email if 'updator_email' in locals() else None,
                        "creator_name": updator_name if 'updator_name' in locals() else "Unknown",
                    },
                },
                ip_address=ip_address if 'ip_address' in locals() else "Unknown"
            )
        except:
            pass
        
        raise HTTPException(status_code=400, detail=error_message)