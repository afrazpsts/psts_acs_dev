from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from DB.db import get_db
from .models import AssignCameraCreate, AssignCameraOut
from utils.security import verify_token

router = APIRouter()


@router.post("/assign_camera", dependencies=[Depends(verify_token)])
def assign_camera(payload: AssignCameraCreate, db: Session = Depends(get_db)):
    try:
        device_exists = db.execute(
            text("SELECT 1 FROM camera_devices WHERE id = :id"),
            {"id": payload.device_id}
        ).first()
        if not device_exists:
            raise HTTPException(status_code=404, detail="Device not found")

        block_exists = db.execute(
            text("SELECT 1 FROM block WHERE id = :id"),
            {"id": payload.block_id}
        ).first()
        if not block_exists:
            raise HTTPException(status_code=404, detail="Block not found")

        result = db.execute(text("""
            INSERT INTO assign_devices (device_id, block_id, created_at)
            VALUES (:device_id, :block_id, NOW())
        """), {
            "device_id": payload.device_id,
            "block_id": payload.block_id
        })
        db.commit()

        inserted_id = result.lastrowid

        inserted = db.execute(text("""
            SELECT ad.id, ad.device_id, ad.block_id, ad.created_at, ad.updated_at,
                   cd.name AS device_name, b.Name AS block_name
            FROM assign_devices ad
            LEFT JOIN camera_devices cd ON ad.device_id = cd.id
            LEFT JOIN block b ON ad.block_id = b.id
            WHERE ad.id = :id
        """), {"id": inserted_id}).mappings().first()

        return inserted

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))



@router.put("/update_assigned_camera/{assign_id}", dependencies=[Depends(verify_token)])
def update_assigned_camera(assign_id: int, payload: AssignCameraCreate, db: Session = Depends(get_db)):
    try:
        device_exists = db.execute(
            text("SELECT 1 FROM camera_devices WHERE id = :id"),
            {"id": payload.device_id}
        ).first()
        if not device_exists:
            raise HTTPException(status_code=404, detail="Device not found")

        block_exists = db.execute(
            text("SELECT 1 FROM block WHERE id = :id"),
            {"id": payload.block_id}
        ).first()
        if not block_exists:
            raise HTTPException(status_code=404, detail="Block not found")

        assignment_exists = db.execute(
            text("SELECT 1 FROM assign_devices WHERE id = :id"),
            {"id": assign_id}
        ).first()
        if not assignment_exists:
            raise HTTPException(status_code=404, detail="Assignment not found")

        db.execute(text("""
            UPDATE assign_devices
            SET device_id = :device_id,
                block_id = :block_id,
                updated_at = NOW()
            WHERE id = :id
        """), {
            "device_id": payload.device_id,
            "block_id": payload.block_id,
            "id": assign_id
        })
        db.commit()

        result = db.execute(text("""
            SELECT ad.id, ad.device_id, ad.block_id, ad.created_at, ad.updated_at,
                   cd.name AS device_name, b.Name AS block_name
            FROM assign_devices ad
            LEFT JOIN camera_devices cd ON ad.device_id = cd.id
            LEFT JOIN block b ON ad.block_id = b.id
            WHERE ad.id = :id
        """), {"id": assign_id}).mappings().first()

        return result

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list_assigned_cameras", dependencies=[Depends(verify_token)])
def list_assigned_cameras(db: Session = Depends(get_db)):
    try:
        query = db.execute(text("""
            SELECT 
                ad.id,
                ad.device_id,
                ad.block_id,
                ad.created_at,
                ad.updated_at,
                cd.name AS device_name,
                b.Name AS block_name
            FROM assign_devices ad
            LEFT JOIN camera_devices cd ON ad.device_id = cd.id
            LEFT JOIN block b ON ad.block_id = b.id
            ORDER BY ad.id DESC
        """))

        results = query.mappings().all()
        return {
            "status": 200,
            "message": "Assigned cameras retrieved successfully.",
            "data": results
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete_assigned_camera/{assign_id}", dependencies=[Depends(verify_token)])
def delete_assigned_camera(assign_id: int, db: Session = Depends(get_db)):
    try:
        result = db.execute(text("SELECT 1 FROM assign_devices WHERE id = :id"), {"id": assign_id}).first()
        if not result:
            raise HTTPException(status_code=404, detail="Assignment not found")

        db.execute(text("DELETE FROM assign_devices WHERE id = :id"), {"id": assign_id})
        db.commit()

        return {
            "status": 200,
            "message": "Assignment deleted successfully."
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
