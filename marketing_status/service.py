from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from DB.db import get_db
from .models import MarketingStatusCreate, MarketingStatusOut
from utils.security import verify_token

router = APIRouter()

@router.post("/create_marketing_status", dependencies=[Depends(verify_token)])
def create_marketing_status(data: MarketingStatusCreate, db: Session = Depends(get_db)):
    try:
        check_sql = text("SELECT id FROM marketing_status WHERE `key` = :key LIMIT 1")
        if db.execute(check_sql, {"key": data.key}).fetchone():
            raise HTTPException(status_code=400, detail="Key already exists")

        insert_sql = text("""
            INSERT INTO marketing_status (`key`, `name`, `description`, created_at, updated_at)
            VALUES (:key, :name, :description, NOW(), NOW())
        """)
        db.execute(insert_sql, {
            "key": data.key,
            "name": data.name,
            "description": data.description
        })
        db.commit()

        last_id = db.execute(text("SELECT LAST_INSERT_ID() AS id")).scalar()
        result = db.execute(
            text("SELECT * FROM marketing_status WHERE id = :id"),
            {"id": last_id}
        ).mappings().first()

        return {
            "status": 200,
            "message": "Marketing status created successfully.",
            "data": result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/list_marketing_status", dependencies=[Depends(verify_token)])
def list_marketing_status(db: Session = Depends(get_db)):
    try:
        query = db.execute(text("""
            SELECT id, `key`, `name`, `description`, created_at, updated_at
            FROM marketing_status
            ORDER BY id DESC
        """))
        results = query.mappings().all()
        return {
            "status": 200,
            "message": "Marketing statuses retrieved successfully.",
            "data": results
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))