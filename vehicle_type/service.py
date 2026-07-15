from fastapi import APIRouter, Depends, HTTPException,Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from DB.db import get_db
from pydantic import BaseModel
from typing import Optional, List
from utils.security import verify_token
from .models import VehicleTypeCreate, VehicleTypeUpdate,VehicleStatusUpdate
from fastapi.responses import JSONResponse



router = APIRouter()



@router.post("/create_vehicle_type", dependencies=[Depends(verify_token)])
def create_vehicle_type(data: VehicleTypeCreate, db: Session = Depends(get_db)):
    try:
        check_sql = text("SELECT id FROM vehicle_type WHERE title = :title LIMIT 1")
        existing = db.execute(check_sql, {"title": data.title}).fetchone()
        
        if existing:
            raise HTTPException(status_code=400, detail="Vehicle type title already exists")

        insert_sql = text("""
            INSERT INTO vehicle_type (title, created_at, updated_at)
            VALUES (:title, NOW(), NOW())
        """)
        db.execute(insert_sql, {"title": data.title})
        db.commit()

        last_id = db.execute(text("SELECT LAST_INSERT_ID() AS id")).scalar()
        result = db.execute(
            text("SELECT id, title, created_at, updated_at FROM vehicle_type WHERE id = :id"),
            {"id": last_id}
        ).mappings().first()

        return {
            "status": 200,
            "message": "Vehicle type created successfully.",
            "data": result
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list_vehicle_type", dependencies=[Depends(verify_token)])
def list_vehicle_type(
    db: Session = Depends(get_db),
    page: int = 1,
    per_page: int = 10,
    search: Optional[str] = None
):
    try:
        offset = (page - 1) * per_page
        
        base_query = """
            SELECT id, title, created_at, updated_at, is_enable
            FROM vehicle_type
        """
        
        params = {}
        filters = []
        
        if search:
            filters.append("title LIKE :search")
            params["search"] = f"%{search}%"
        
        if filters:
            base_query += " WHERE " + " AND ".join(filters)
        
        count_query = f"SELECT COUNT(*) FROM vehicle_type"
        if filters:
            count_query += " WHERE " + " AND ".join(filters)
        
        total_count = db.execute(text(count_query), params).scalar() or 0
        last_page = (total_count + per_page - 1) // per_page if total_count > 0 else 1
        
        base_query += " ORDER BY id DESC LIMIT :limit OFFSET :offset"
        params.update({"limit": per_page, "offset": offset})
        
        results = db.execute(text(base_query), params).mappings().all()
        
        return {
            "status": 200,
            "message": "Vehicle types retrieved successfully.",
            "data": [dict(row) for row in results],
            "pagination_details": {
                "page": page,
                "per_page": per_page,
                "total": total_count,
                "last_page": last_page
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/get_vehicle_type/{vehicle_type_id}", dependencies=[Depends(verify_token)])
def get_vehicle_type(vehicle_type_id: int, db: Session = Depends(get_db)):
    try:
        query = text("""
            SELECT id, title, created_at, updated_at
            FROM vehicle_type
            WHERE id = :id
        """)
        result = db.execute(query, {"id": vehicle_type_id}).mappings().first()
        
        if not result:
            raise HTTPException(status_code=404, detail="Vehicle type not found")
        
        return {
            "status": 200,
            "message": "Vehicle type retrieved successfully.",
            "data": dict(result)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/update_vehicle_type/{vehicle_type_id}", dependencies=[Depends(verify_token)])
def update_vehicle_type(
    vehicle_type_id: int, 
    data: VehicleTypeUpdate, 
    db: Session = Depends(get_db)
):
    try:
        check_query = text("SELECT id FROM vehicle_type WHERE id = :id")
        existing = db.execute(check_query, {"id": vehicle_type_id}).fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Vehicle type not found")
        
        if data.title:
            title_check = text("SELECT id FROM vehicle_type WHERE title = :title AND id != :id")
            title_exists = db.execute(title_check, {"title": data.title, "id": vehicle_type_id}).fetchone()
            
            if title_exists:
                raise HTTPException(status_code=400, detail="Vehicle type title already exists")
        
        update_fields = []
        params = {"id": vehicle_type_id}
        
        if data.title is not None:
            update_fields.append("title = :title")
            params["title"] = data.title
        
        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        update_fields.append("updated_at = NOW()")
        
        update_query = text(f"""
            UPDATE vehicle_type 
            SET {', '.join(update_fields)}
            WHERE id = :id
        """)
        
        db.execute(update_query, params)
        db.commit()
        
        result = db.execute(
            text("SELECT id, title, created_at, updated_at FROM vehicle_type WHERE id = :id"),
            {"id": vehicle_type_id}
        ).mappings().first()
        
        return {
            "status": 200,
            "message": "Vehicle type updated successfully.",
            "data": dict(result)
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete_vehicle_type/{vehicle_type_id}", dependencies=[Depends(verify_token)])
def delete_vehicle_type(vehicle_type_id: int, db: Session = Depends(get_db)):
    try:
        check_query = text("SELECT id FROM vehicle_type WHERE id = :id")
        existing = db.execute(check_query, {"id": vehicle_type_id}).fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Vehicle type not found")
        
       
        delete_query = text("DELETE FROM vehicle_type WHERE id = :id")
        db.execute(delete_query, {"id": vehicle_type_id})
        db.commit()
        
        return {
            "status": 200,
            "message": "Vehicle type deleted successfully."
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all_vehicle_types", dependencies=[Depends(verify_token)])
def get_all_vehicle_types(db: Session = Depends(get_db)):
    """Get all vehicle types without pagination (for dropdowns)"""
    try:
        query = text("""
            SELECT id, title
            FROM vehicle_type
            ORDER BY title ASC
        """)
        results = db.execute(query).mappings().all()
        
        return {
            "status": 200,
            "message": "Vehicle types retrieved successfully.",
            "data": [dict(row) for row in results]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/update_vehicle_type_status/{vehicle_type_id}", dependencies=[Depends(verify_token)])
def update_vehicle_type_status(
    vehicle_type_id: int,
    payload: VehicleStatusUpdate,
    db: Session = Depends(get_db)
):
    try:
        is_enable = payload.is_enable

        check_query = text("SELECT id, title FROM vehicle_type WHERE id = :id")
        existing = db.execute(check_query, {"id": vehicle_type_id}).mappings().first()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Vehicle type not found")
        
        update_query = text("""
            UPDATE vehicle_type 
            SET is_enable = :is_enable, updated_at = NOW()
            WHERE id = :id
        """)
        
        db.execute(update_query, {"is_enable": is_enable, "id": vehicle_type_id})
        db.commit()
        
        return {
            "status": 200,
            "message": f"Vehicle type '{existing['title']}' has been {'activated' if is_enable else 'deactivated'} successfully.",
            "data": {
                "id": vehicle_type_id,
                "title": existing["title"],
                "is_enable": is_enable,
                "status": "active" if is_enable else "inactive"
            }
        }

    except HTTPException as e:
        db.rollback()
        raise e  

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))