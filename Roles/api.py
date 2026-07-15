from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Optional
from common.logger import log as write_to_server_log

from DB.db import get_db
from activity_logs.service import log_activity
from .service import (
    create_role_service,
    delete_role_service,
    get_role_by_id_service,
    list_roles_service,
    update_role_service,
    update_role_status_service,
)


router = APIRouter(prefix="/roles", tags=["Roles"])


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


@router.post("/create_role")
def create_role(
    request: Request,
    payload: dict,
    creator_email: Optional[str] = Query(None, description="Email of the person creating the role"),
    db: Session = Depends(get_db),
):
    try:
        ip_address = request.client.host if request and request.client else "Unknown"

        creator_id, creator_name, creator_company_id = _resolve_actor_from_email(db, creator_email)

        title = payload.get("title")
        
        if not title:
            raise HTTPException(status_code=400, detail="Role title is required")
        
        result = create_role_service(title=title, db=db)

        log_user_id = creator_id if creator_id is not None else 1
        log_activity(
            db=db,
            user_id=log_user_id,
            action="Create",
            module_name="Roles",
            record_id=result.get("id") if isinstance(result, dict) else None,
            description=f"Role created successfully – {title}",
            new_data={
                "payload": {"title": title},
                "result": {"status": 201, "message": "Role created successfully", "data": result},
                "creator_info": {
                    "creator_id": creator_id,
                    "creator_email": creator_email,
                    "creator_name": creator_name,
                    "creator_company_id": creator_company_id,
                },
            },
            ip_address=ip_address,
        )

        return {
            "message": "Role created successfully",
            "data": result,
            "status": 201,
            "creator_info": {
                "id": creator_id,
                "email": creator_email,
                "name": creator_name,
                "company_id": creator_company_id,
            },
        }
        
    except HTTPException as he:
        try:
            log_activity(
                db=db,
                user_id=creator_id if 'creator_id' in locals() else None,
                action="Create Role Failed",
                module_name="Roles",
                description=f"Role creation failed: {he.detail}",
                new_data={
                    "payload": payload,
                    "error": he.detail,
                    "creator_info": {
                        "creator_id": creator_id if 'creator_id' in locals() else None,
                        "creator_email": creator_email if 'creator_email' in locals() else None,
                        "creator_name": creator_name if 'creator_name' in locals() else "Unknown",
                    },
                },
                ip_address=ip_address if 'ip_address' in locals() else "Unknown"
            )
        except:
            pass
        raise he
        
    except Exception as e:
        error_message = str(e)
        write_to_server_log(f"Error in create_role: {error_message}")
        
        try:
            log_activity(
                db=db,
                user_id=creator_id if 'creator_id' in locals() else None,
                action="Create Role Failed",
                module_name="Roles",
                description=f"Error: {error_message}",
                new_data={
                    "payload": payload,
                    "error": error_message,
                    "creator_info": {
                        "creator_id": creator_id if 'creator_id' in locals() else None,
                        "creator_email": creator_email if 'creator_email' in locals() else None,
                        "creator_name": creator_name if 'creator_name' in locals() else "Unknown",
                    },
                },
                ip_address=ip_address if 'ip_address' in locals() else "Unknown"
            )
        except:
            pass
        
        raise HTTPException(status_code=400, detail=error_message)


@router.get("/get_role/{role_id}")
def get_role(role_id: int, db: Session = Depends(get_db)):
    try:
        result = get_role_by_id_service(role_id, db)
        if not result:
            raise HTTPException(status_code=404, detail="Role not found")
        return {"message": "Role retrieved successfully", "data": result, "status": 200}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/get_roles")
def get_roles(
    request: Request,
    searchdata: Optional[str] = Query(None, description="Search in role title"),
    pagination: Optional[bool] = Query(True, description="Enable/disable pagination"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page"),
    from_date: Optional[str] = Query(None, description="Filter from this date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="Filter to this date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Get all roles with pagination and filtering options.
    Excludes Super Admin role from the response.
    Supports search in title and date range filtering.
    Use pagination=false to get all records without pagination.
    """
    try:
        ip_address = request.client.host if request and request.client else "Unknown"
        
        write_to_server_log(f"API: Getting roles with filters - search: {searchdata}, pagination: {pagination}, page: {page}, per_page: {per_page}")
        
        result = list_roles_service(
            db=db,
            searchdata=searchdata,
            from_date=from_date,
            to_date=to_date,
            pagination=pagination,
            page=page if pagination else 1,
            per_page=per_page if pagination else None
        )
        
        response_data = {
            "message": "Roles retrieved successfully",
            "data": result['roles'], 
            "filters_applied": {
                "searchdata": searchdata,
                "from_date": from_date,
                "to_date": to_date
            },
            "status": 200
        }
        
        if pagination:
            last_page = result['total_pages']
            
            response_data["pagination_details"] = {
                "page": page,
                "per_page": per_page,
                "total": result['total'],
                "last_page": last_page
            }
            
            log_activity(
                db=db,
                user_id=None,
                action="List Roles",
                module_name="Roles",
                description=f"Retrieved paginated list of roles - Page: {page}, Total: {result['total']} (Excluding Super Admin)",
                new_data={
                    "filters": {
                        "searchdata": searchdata,
                        "from_date": from_date,
                        "to_date": to_date
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
        else:
            log_activity(
                db=db,
                user_id=None,
                action="List All Roles",
                module_name="Roles",
                description=f"Retrieved all roles - Total: {len(result['roles'])} (Excluding Super Admin)",
                new_data={
                    "filters": {
                        "searchdata": searchdata,
                        "from_date": from_date,
                        "to_date": to_date
                    },
                    "total_records": len(result['roles'])
                },
                ip_address=ip_address
            )
        
        return response_data
        
    except HTTPException as he:
        raise he
    except Exception as e:
        error_message = str(e)
        write_to_server_log(f"Error in get_roles: {error_message}")
        import traceback
        write_to_server_log(f"Traceback: {traceback.format_exc()}")
        
        try:
            log_activity(
                db=db,
                user_id=None,
                action="List Roles Failed",
                module_name="Roles",
                description=f"Error while listing roles: {error_message}",
                new_data={
                    "error": error_message,
                    "filters": {
                        "searchdata": searchdata,
                        "from_date": from_date,
                        "to_date": to_date
                    },
                    "pagination": pagination
                },
                ip_address=ip_address if 'ip_address' in locals() else "Unknown"
            )
        except:
            pass
        
        raise HTTPException(status_code=500, detail=f"Error retrieving roles: {error_message}")


@router.put("/update_role/{role_id}")
def update_role(
    request: Request,
    role_id: int,
    payload: dict,
    updater_email: Optional[str] = Query(None, description="Email of the person updating the role"),
    db: Session = Depends(get_db),
):
    try:
        ip_address = request.client.host if request and request.client else "Unknown"
        updator_id, updator_name, updator_company_id = _resolve_actor_from_email(db, updater_email)

        old_role = get_role_by_id_service(role_id, db)
        if not old_role:
            raise HTTPException(status_code=404, detail="Role not found")

        result = update_role_service(role_id, payload, db)
        if not result:
            raise HTTPException(status_code=404, detail="Role not found")

        log_user_id = updator_id if updator_id is not None else 1
        log_activity(
            db=db,
            user_id=log_user_id,
            action="Update",
            module_name="Roles",
            record_id=role_id,
            description="Role updated successfully" + (f" – {payload.get('title')}" if payload.get("title") else ""),
            old_data={"role": old_role},
            new_data={
                "payload": {"role_id": role_id, **payload},
                "result": {"status": 200, "message": "Role updated successfully", "data": result},
                "creator_info": {
                    "creator_id": updator_id,
                    "creator_email": updater_email,
                    "creator_name": updator_name,
                    "creator_company_id": updator_company_id,
                },
            },
            ip_address=ip_address,
        )

        return {
            "message": "Role updated successfully",
            "data": result,
            "status": 200,
            "creator_info": {
                "id": updator_id,
                "email": updater_email,
                "name": updator_name,
                "company_id": updator_company_id,
            },
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/delete_role/{role_id}")
def delete_role(
    request: Request,
    role_id: int,
    deleter_email: Optional[str] = Query(None, description="Email of the person deleting the role"),
    db: Session = Depends(get_db),
):
    try:
        ip_address = request.client.host if request and request.client else "Unknown"
        deleter_id, deleter_name, deleter_company_id = _resolve_actor_from_email(db, deleter_email)

        old_role = get_role_by_id_service(role_id, db)
        if not old_role:
            raise HTTPException(status_code=404, detail="Role not found")

        result = delete_role_service(role_id, db)
        if not result:
            raise HTTPException(status_code=404, detail="Role not found")

        log_user_id = deleter_id if deleter_id is not None else 1
        log_activity(
            db=db,
            user_id=log_user_id,
            action="Delete",
            module_name="Roles",
            record_id=role_id,
            description="Role deleted successfully" + (f" – {old_role.get('title')}" if old_role.get("title") else ""),
            old_data={"role": old_role},
            new_data={
                "payload": {"role_id": role_id},
                "result": {"status": 200, "message": "Role deleted successfully", "data": result},
                "creator_info": {
                    "creator_id": deleter_id,
                    "creator_email": deleter_email,
                    "creator_name": deleter_name,
                    "creator_company_id": deleter_company_id,
                },
            },
            ip_address=ip_address,
        )

        return {
            "message": "Role deleted successfully",
            "data": result,
            "status": 200,
            "creator_info": {
                "id": deleter_id,
                "email": deleter_email,
                "name": deleter_name,
                "company_id": deleter_company_id,
            },
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/update_role_status/{role_id}")
def update_role_status(
    request: Request,
    role_id: int,
    payload: dict,
    updater_email: Optional[str] = Query(None, description="Email of the person updating the role status"),
    db: Session = Depends(get_db),
):
    """
    Update role active status (is_role_active)
    Accepts true/false or 1/0
    """
    try:
        ip_address = request.client.host if request and request.client else "Unknown"
        updator_id, updator_name, updator_company_id = _resolve_actor_from_email(db, updater_email)

        old_role = get_role_by_id_service(role_id, db)
        if not old_role:
            raise HTTPException(status_code=404, detail="Role not found")
        
        is_role_active = payload.get("is_role_active")
        
        if is_role_active is None:
            raise HTTPException(status_code=400, detail="is_role_active field is required")
        
        if isinstance(is_role_active, bool):
            is_role_active_int = 1 if is_role_active else 0
        elif isinstance(is_role_active, int):
            if is_role_active not in [0, 1]:
                raise HTTPException(status_code=400, detail="is_role_active must be 0, 1, true, or false")
            is_role_active_int = is_role_active
        elif isinstance(is_role_active, str):
            if is_role_active.lower() in ['true', '1']:
                is_role_active_int = 1
            elif is_role_active.lower() in ['false', '0']:
                is_role_active_int = 0
            else:
                raise HTTPException(status_code=400, detail="is_role_active must be true/false or 1/0")
        else:
            raise HTTPException(status_code=400, detail="is_role_active must be a boolean, integer, or string")
        
        if role_id == 1 and is_role_active_int == 0:
            raise HTTPException(status_code=400, detail="Cannot deactivate Super Admin role")
        
        result = update_role_status_service(role_id, is_role_active_int, db)
        
        if not result:
            raise HTTPException(status_code=404, detail="Role not found")
        
        log_user_id = updator_id if updator_id is not None else 1
        status_text = "activated" if is_role_active_int == 1 else "deactivated"
        
        log_activity(
            db=db,
            user_id=log_user_id,
            action="Update Status",
            module_name="Roles",
            record_id=role_id,
            description=f"Role {status_text} successfully – {old_role.get('title')}",
            old_data={"role": old_role, "is_role_active": old_role.get("is_role_active")},
            new_data={
                "payload": {"role_id": role_id, "is_role_active": is_role_active},
                "result": {
                    "status": 200, 
                    "message": f"Role {status_text} successfully", 
                    "data": result
                },
                "creator_info": {
                    "creator_id": updator_id,
                    "creator_email": updater_email,
                    "creator_name": updator_name,
                    "creator_company_id": updator_company_id,
                },
            },
            ip_address=ip_address,
        )
        
        return {
            "message": f"Role {status_text} successfully",
            "data": result,
            "status": 200,
            "creator_info": {
                "id": updator_id,
                "email": updater_email,
                "name": updator_name,
                "company_id": updator_company_id,
            },
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        error_message = str(e)
        write_to_server_log(f"Error in update_role_status: {error_message}")
        import traceback
        write_to_server_log(f"Traceback: {traceback.format_exc()}")
        
        # Log error activity
        try:
            log_activity(
                db=db,
                user_id=updator_id if 'updator_id' in locals() else None,
                action="Update Role Status Failed",
                module_name="Roles",
                description=f"Error while updating role status: {error_message}",
                new_data={
                    "role_id": role_id,
                    "payload": payload,
                    "error": error_message,
                    "creator_info": {
                        "creator_id": updator_id if 'updator_id' in locals() else None,
                        "creator_email": updater_email if 'updater_email' in locals() else None,
                        "creator_name": updator_name if 'updator_name' in locals() else "Unknown",
                    },
                },
                ip_address=ip_address if 'ip_address' in locals() else "Unknown"
            )
        except:
            pass
        
        raise HTTPException(status_code=400, detail=error_message)