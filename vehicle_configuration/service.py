from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from common.logger import log as write_to_server_log
from typing import Optional, List


def create_vehicle_configuration_service(
    no_of_vehicle_free_slot: str,
    vehicle_configurations: List[dict],
    db: Session
):
    """
    Service function to create or update vehicle configurations (UPSERT)
    """
    created_configs = []
    
    try:
        for vc in vehicle_configurations:
            vehicle_type_id = vc.get("vehicle_type_id")
            amount = vc.get("amount")
            billing_period = vc.get("billing_period")
            
            # Handle billing_period: if empty string or None, set to None (NULL in DB)
            if billing_period == "" or billing_period is None:
                billing_period = None
            
            # Handle amount: if None, set to 0
            if amount is None:
                amount = 0
            
            # Check if record exists for this vehicle_type_id
            existing = db.execute(
                text("""
                    SELECT id FROM vehicle_configurations 
                    WHERE vehicle_type_id = :vehicle_type_id
                """),
                {"vehicle_type_id": vehicle_type_id}
            ).first()
            
            if existing:
                # Update existing record
                update_query = """
                    UPDATE vehicle_configurations 
                    SET no_of_vehicle_free_slot = :no_of_vehicle_free_slot,
                        Amount = :Amount, 
                        billing_period = :billing_period, 
                        updated_at = NOW()
                    WHERE vehicle_type_id = :vehicle_type_id
                """
                db.execute(
                    text(update_query),
                    {
                        "no_of_vehicle_free_slot": no_of_vehicle_free_slot,
                        "vehicle_type_id": vehicle_type_id,
                        "Amount": amount,
                        "billing_period": billing_period
                    }
                )
            else:
                # Insert new record
                insert_query = """
                    INSERT INTO vehicle_configurations (
                        no_of_vehicle_free_slot, 
                        vehicle_type_id, 
                        Amount, 
                        billing_period, 
                        created_at, 
                        updated_at
                    ) VALUES (
                        :no_of_vehicle_free_slot, 
                        :vehicle_type_id, 
                        :Amount, 
                        :billing_period, 
                        NOW(), 
                        NOW()
                    )
                """
                db.execute(
                    text(insert_query),
                    {
                        "no_of_vehicle_free_slot": no_of_vehicle_free_slot,
                        "vehicle_type_id": vehicle_type_id,
                        "Amount": amount,
                        "billing_period": billing_period
                    }
                )
            
            # Get the created/updated record
            created = db.execute(
                text("""
                    SELECT id, no_of_vehicle_free_slot, vehicle_type_id, Amount, billing_period,
                           DATE_FORMAT(created_at, '%Y-%m-%dT%H:%i:%s') as created_at,
                           DATE_FORMAT(updated_at, '%Y-%m-%dT%H:%i:%s') as updated_at
                    FROM vehicle_configurations 
                    WHERE vehicle_type_id = :vehicle_type_id
                """),
                {"vehicle_type_id": vehicle_type_id}
            ).mappings().first()
            
            if created:
                created_configs.append(dict(created))
        
        db.commit()
        write_to_server_log(f"Created/Updated {len(created_configs)} vehicle configurations")
        
        # Return in the same format as get API
        return {
            "no_of_vehicle_free_slot": no_of_vehicle_free_slot,
            "vehicle_configurations": [
                {
                    "vehicle_type_id": str(config['vehicle_type_id']),
                    "amount": str(config['Amount']) if config['Amount'] else None,
                    "billing_period": config['billing_period']
                }
                for config in created_configs
            ]
        }
        
    except Exception as e:
        db.rollback()
        error_msg = str(e)
        write_to_server_log(f"Error in create_vehicle_configuration_service: {error_msg}")
        import traceback
        write_to_server_log(f"Traceback: {traceback.format_exc()}")
        raise Exception(f"Failed to create/update vehicle configurations: {error_msg}")


def get_vehicle_configuration_by_id_service(config_id: int, db: Session):
    """Get vehicle configuration by ID"""
    result = db.execute(
        text("""
            SELECT id, no_of_vehicle_free_slot, vehicle_type_id, Amount,
                   DATE_FORMAT(created_at, '%Y-%m-%dT%H:%i:%s') as created_at,
                   DATE_FORMAT(updated_at, '%Y-%m-%dT%H:%i:%s') as updated_at
            FROM vehicle_configurations 
            WHERE id = :id
        """),
        {"id": config_id},
    ).mappings().first()
    return dict(result) if result else None


def get_all_vehicle_configurations_by_free_slot(db: Session, no_of_vehicle_free_slot: str):
    """Get all vehicle configurations with same free slot value"""
    result = db.execute(
        text("""
            SELECT id, no_of_vehicle_free_slot, vehicle_type_id, Amount,
                   DATE_FORMAT(created_at, '%Y-%m-%dT%H:%i:%s') as created_at,
                   DATE_FORMAT(updated_at, '%Y-%m-%dT%H:%i:%s') as updated_at
            FROM vehicle_configurations 
            WHERE no_of_vehicle_free_slot = :no_of_vehicle_free_slot
            ORDER BY id ASC
        """),
        {"no_of_vehicle_free_slot": no_of_vehicle_free_slot},
    ).mappings().all()
    return [dict(r) for r in result]


def list_vehicle_configurations_service(
    db: Session,
    searchdata: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    no_of_free_slots_param: Optional[str] = None
):
    """
    Service function to list all vehicle types with their configurations
    Returns all vehicle types with amount and billing_period (null if not configured)
    No pagination - returns all records.
    """
    try:
        # Get the no_of_vehicle_free_slot (use param or get from DB)
        if no_of_free_slots_param:
            no_of_free_slots = no_of_free_slots_param
        else:
            free_slot_query = """
                SELECT DISTINCT no_of_vehicle_free_slot 
                FROM vehicle_configurations 
                LIMIT 1
            """
            free_slot_result = db.execute(text(free_slot_query)).first()
            no_of_free_slots = str(free_slot_result[0]) if free_slot_result else "0"
        
        # Base query to get all vehicle types with their configurations (if any)
        base_query = """
            SELECT 
                vt.id as vehicle_type_id,
                vt.title as vehicle_type_title,
                vc.Amount as amount,
                vc.billing_period,
                vc.no_of_vehicle_free_slot,
                DATE_FORMAT(vc.created_at, '%Y-%m-%dT%H:%i:%s') as created_at,
                DATE_FORMAT(vc.updated_at, '%Y-%m-%dT%H:%i:%s') as updated_at
            FROM vehicle_type vt
            LEFT JOIN vehicle_configurations vc 
                ON vt.id = vc.vehicle_type_id 
                AND vc.no_of_vehicle_free_slot = :no_of_free_slots
            WHERE vt.is_enable = 1
        """
        
        params = {"no_of_free_slots": no_of_free_slots}
        
        # Apply search filter on vehicle type title
        if searchdata:
            base_query += " AND vt.title LIKE :search"
            params["search"] = f"%{searchdata}%"
        
        # Apply date filters (on configuration creation date)
        if from_date:
            base_query += " AND DATE(vc.created_at) >= :from_date"
            params["from_date"] = from_date
            
        if to_date:
            base_query += " AND DATE(vc.created_at) <= :to_date"
            params["to_date"] = to_date
        
        # Add order by
        base_query += " ORDER BY vt.id ASC"
        
        result = db.execute(text(base_query), params).mappings().all()
        
        # Format the response
        vehicle_configurations = []
        for row in result:
            config = {
                "vehicle_type_id": str(row['vehicle_type_id']),
                "vehicle_type_title": row['vehicle_type_title'],
                "amount": str(row['amount']) if row['amount'] is not None else None,
                "billing_period": row['billing_period'] if row['billing_period'] is not None else None
            }
            vehicle_configurations.append(config)
        
        # Prepare response (no pagination fields)
        response_data = {
            "no_of_vehicle_free_slot": no_of_free_slots,
            "vehicle_configurations": vehicle_configurations
        }
        
        return response_data
        
    except Exception as e:
        write_to_server_log(f"Error in list_vehicle_configurations_service: {str(e)}")
        import traceback
        write_to_server_log(f"Traceback: {traceback.format_exc()}")
        raise Exception(f"Error in list_vehicle_configurations_service: {str(e)}")


def update_vehicle_configuration_service(config_id: int, payload: dict, db: Session):
    """
    Service function to update a vehicle configuration
    """
    existing = get_vehicle_configuration_by_id_service(config_id, db)
    if not existing:
        return None

    update_fields = []
    params = {"id": config_id}


    if "vehicle_type_id" in payload and payload["vehicle_type_id"]:
        new_type = payload["vehicle_type_id"]
        if new_type != existing.get("vehicle_type_id"):
            duplicate_check = db.execute(
                text("SELECT id FROM vehicle_configurations WHERE vehicle_type_id = :vehicle_type_id AND id != :id"),
                {"vehicle_type_id": new_type, "id": config_id}
            ).first()
            if duplicate_check:
                raise Exception(f"Vehicle configuration with type '{new_type}' already exists")
        update_fields.append("vehicle_type_id = :vehicle_type_id")
        params["vehicle_type_id"] = new_type

    if "no_of_vehicle_free_slot" in payload:
        update_fields.append("no_of_vehicle_free_slot = :no_of_vehicle_free_slot")
        params["no_of_vehicle_free_slot"] = payload.get("no_of_vehicle_free_slot")

    if "amount" in payload:
        update_fields.append("Amount = :amount")
        params["amount"] = payload.get("amount")

    if not update_fields:
        return existing

    update_fields.append("updated_at = NOW()")

    try:
        db.execute(
            text(
                f"""
                UPDATE vehicle_configurations
                SET {", ".join(update_fields)}
                WHERE id = :id
                """
            ),
            params,
        )
        db.commit()
        write_to_server_log(f"Vehicle configuration {config_id} updated successfully")
        return get_vehicle_configuration_by_id_service(config_id, db)
    except Exception as e:
        db.rollback()
        error_msg = str(e)
        write_to_server_log(f"Error in update_vehicle_configuration_service: {error_msg}")
        raise Exception(f"Failed to update vehicle configuration: {error_msg}")


def delete_vehicle_configuration_service(config_id: int, db: Session):
    """
    Service function to delete a vehicle configuration
    """
    existing = get_vehicle_configuration_by_id_service(config_id, db)
    if not existing:
        return None

    try:
        db.execute(text("DELETE FROM vehicle_configurations WHERE id = :id"), {"id": config_id})
        db.commit()
        write_to_server_log(f"Vehicle configuration {config_id} deleted successfully")
        return {"id": config_id, "deleted": True}
    except Exception as e:
        db.rollback()
        error_msg = str(e)
        write_to_server_log(f"Error in delete_vehicle_configuration_service: {error_msg}")
        raise Exception(f"Failed to delete vehicle configuration: {error_msg}")