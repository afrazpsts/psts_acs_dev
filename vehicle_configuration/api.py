from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Optional, List
from common.logger import log as write_to_server_log

from DB.db import get_db
from activity_logs.service import log_activity
from .models import (
    VehicleConfigurationCreate, 
    VehicleConfigurationUpdate, 
    VehicleConfigurationResponse,
    VehicleConfigurationListResponse
)
from .service import (
    create_vehicle_configuration_service,
    delete_vehicle_configuration_service,
    get_vehicle_configuration_by_id_service,
    list_vehicle_configurations_service,
    update_vehicle_configuration_service,
)


router = APIRouter(prefix="/vehicle-configurations", tags=["Vehicle Configurations"])


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


@router.post("/create_vehicle_configuration", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_vehicle_configuration(
    request: Request,
    payload: VehicleConfigurationCreate,
    creator_email: Optional[str] = Query(None, description="Email of the person creating the vehicle configuration"),
    db: Session = Depends(get_db),
):
    try:
        ip_address = request.client.host if request and request.client else "Unknown"

        creator_id, creator_name, creator_company_id = _resolve_actor_from_email(db, creator_email)
        
        # Convert Pydantic model to dict with proper field names
        vehicle_configs = []
        for vc in payload.vehicle_configurations:
            config_dict = {
                "vehicle_type_id": vc.vehicle_type_id,
                "amount": vc.amount,
                "billing_period": vc.billing_period  # Include billing_period
            }
            vehicle_configs.append(config_dict)
        
        result = create_vehicle_configuration_service(
            no_of_vehicle_free_slot=payload.no_of_vehicle_free_slot,
            vehicle_configurations=vehicle_configs,
            db=db
        )

        log_user_id = creator_id if creator_id is not None else 1
        log_activity(
            db=db,
            user_id=log_user_id,
            action="Create",
            module_name="Vehicle Configurations",
            record_id=None,
            description=f"Vehicle configurations created successfully - {len(payload.vehicle_configurations)} types",
            new_data={
                "payload": payload.dict(),
                "result": {"status": 200, "message": "Vehicle configurations created successfully", "data": result},
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
            "message": "Vehicle configurations created successfully",
            "data": result,
            "status": 200,
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
                action="Create Vehicle Configuration Failed",
                module_name="Vehicle Configurations",
                description=f"Vehicle configuration creation failed: {he.detail}",
                new_data={
                    "payload": payload.dict() if payload else {},
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
        write_to_server_log(f"Error in create_vehicle_configuration: {error_message}")
        
        try:
            log_activity(
                db=db,
                user_id=creator_id if 'creator_id' in locals() else None,
                action="Create Vehicle Configuration Failed",
                module_name="Vehicle Configurations",
                description=f"Error: {error_message}",
                new_data={
                    "payload": payload.dict() if payload else {},
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


@router.get("/get_vehicle_configuration/{config_id}", response_model=dict)
def get_vehicle_configuration(config_id: int, db: Session = Depends(get_db)):
    try:
        result = get_vehicle_configuration_by_id_service(config_id, db)
        if not result:
            raise HTTPException(status_code=404, detail="Vehicle configuration not found")
        return {"message": "Vehicle configuration retrieved successfully", "data": result, "status": 200}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/get_vehicle_configurations")
def get_vehicle_configurations(
    request: Request,
    searchdata: Optional[str] = Query(None, description="Search in vehicle type title"),
    no_of_vehicle_free_slot: Optional[str] = Query(None, description="Filter by no of vehicle free slot"),
    from_date: Optional[str] = Query(None, description="Filter from this date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="Filter to this date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Get all vehicle types with their configurations for the specified free slot.
    Returns all vehicle types - configured ones have amount/billing_period, unconfigured have null.
    No pagination - returns all records.
    """
    try:
        ip_address = request.client.host if request and request.client else "Unknown"
        
        write_to_server_log(f"API: Getting vehicle configurations - search: {searchdata}, free_slot: {no_of_vehicle_free_slot}")
        
        result = list_vehicle_configurations_service(
            db=db,
            searchdata=searchdata,
            from_date=from_date,
            to_date=to_date,
            no_of_free_slots_param=no_of_vehicle_free_slot
        )
        
        response_data = {
            "message": "Vehicle configurations retrieved successfully",
            "data": {
                "no_of_vehicle_free_slot": result['no_of_vehicle_free_slot'],
                "vehicle_configurations": result['vehicle_configurations']
            },
            "filters_applied": {
                "searchdata": searchdata,
                "no_of_vehicle_free_slot": no_of_vehicle_free_slot,
                "from_date": from_date,
                "to_date": to_date
            },
            "status": 200
        }
        
        # Log activity
        log_activity(
            db=db,
            user_id=None,
            action="List Vehicle Configurations",
            module_name="Vehicle Configurations",
            description=f"Retrieved vehicle configurations - Search: {searchdata}, Free Slots: {no_of_vehicle_free_slot}",
            new_data={
                "filters": {
                    "searchdata": searchdata,
                    "no_of_vehicle_free_slot": no_of_vehicle_free_slot,
                    "from_date": from_date,
                    "to_date": to_date
                }
            },
            ip_address=ip_address
        )
        
        return response_data
        
    except HTTPException as he:
        raise he
    except Exception as e:
        error_message = str(e)
        write_to_server_log(f"Error in get_vehicle_configurations: {error_message}")
        import traceback
        write_to_server_log(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error retrieving vehicle configurations: {error_message}")


@router.put("/update_vehicle_configuration/{config_id}", response_model=dict)
def update_vehicle_configuration(
    request: Request,
    config_id: int,
    payload: VehicleConfigurationUpdate,
    updater_email: Optional[str] = Query(None, description="Email of the person updating the vehicle configuration"),
    db: Session = Depends(get_db),
):
    try:
        ip_address = request.client.host if request and request.client else "Unknown"
        updator_id, updator_name, updator_company_id = _resolve_actor_from_email(db, updater_email)

        old_config = get_vehicle_configuration_by_id_service(config_id, db)
        if not old_config:
            raise HTTPException(status_code=404, detail="Vehicle configuration not found")

        result = update_vehicle_configuration_service(config_id, payload.dict(exclude_none=True), db)
        if not result:
            raise HTTPException(status_code=404, detail="Vehicle configuration not found")

        log_user_id = updator_id if updator_id is not None else 1
        log_activity(
            db=db,
            user_id=log_user_id,
            action="Update",
            module_name="Vehicle Configurations",
            record_id=config_id,
            description="Vehicle configuration updated successfully",
            old_data={"configuration": old_config},
            new_data={
                "payload": {"config_id": config_id, **payload.dict(exclude_none=True)},
                "result": {"status": 200, "message": "Vehicle configuration updated successfully", "data": result},
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
            "message": "Vehicle configuration updated successfully",
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


@router.delete("/delete_vehicle_configuration/{config_id}", response_model=dict)
def delete_vehicle_configuration(
    request: Request,
    config_id: int,
    deleter_email: Optional[str] = Query(None, description="Email of the person deleting the vehicle configuration"),
    db: Session = Depends(get_db),
):
    try:
        ip_address = request.client.host if request and request.client else "Unknown"
        deleter_id, deleter_name, deleter_company_id = _resolve_actor_from_email(db, deleter_email)

        old_config = get_vehicle_configuration_by_id_service(config_id, db)
        if not old_config:
            raise HTTPException(status_code=404, detail="Vehicle configuration not found")

        result = delete_vehicle_configuration_service(config_id, db)
        if not result:
            raise HTTPException(status_code=404, detail="Vehicle configuration not found")

        log_user_id = deleter_id if deleter_id is not None else 1
        log_activity(
            db=db,
            user_id=log_user_id,
            action="Delete",
            module_name="Vehicle Configurations",
            record_id=config_id,
            description=f"Vehicle configuration deleted successfully – {old_config.get('vehicle_type_id')}",
            old_data={"configuration": old_config},
            new_data={
                "payload": {"config_id": config_id},
                "result": {"status": 200, "message": "Vehicle configuration deleted successfully", "data": result},
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
            "message": "Vehicle configuration deleted successfully",
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