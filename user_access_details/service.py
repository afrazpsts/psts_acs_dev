from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from DB.db import SessionLocal
from utils.security import verify_token
from datetime import datetime
import traceback

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/list_access_details", dependencies=[Depends(verify_token)])
async def list_access_details(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1)
):
    try:
        per_page = 10
        offset = (page - 1) * per_page

        total = db.execute(text("SELECT COUNT(*) FROM user_access_details")).scalar()
        result = db.execute(text(f"""
            SELECT id, residency_type_id, building_id, level_id, unit_id,
                   join_date, access_start, access_end
            FROM user_access_details
            ORDER BY id DESC
            LIMIT {per_page} OFFSET {offset}
        """))
        rows = result.fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail="No access details found.")

        data = []
        for row in rows:
            data.append({
                "id": row[0],
                "residency_type_id": row[1],
                "building_id": row[2],
                "level_id": row[3],
                "unit_id": row[4],
                "join_date": row[5],
                "access_start": row[6],
                "access_end": row[7],
            })

        return {
            "status": 200,
            "data": data,
            "page": page,
            "per_page": per_page,
            "total": total,
            "message": "Access details retrieved successfully."
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.post("/create_access_detail", dependencies=[Depends(verify_token)])
async def create_access_detail(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()

        query = text("""
            INSERT INTO user_access_details 
            (residency_type_id, building_id, level_id, unit_id, join_date, access_start, access_end)
            VALUES 
            (:residency_type_id, :building_id, :level_id, :unit_id, :join_date, :access_start, :access_end)
        """)

        db.execute(query, {
            "residency_type_id": data["residency_type_id"],
            "building_id": data["building_id"],
            "level_id": data["level_id"],
            "unit_id": data["unit_id"],
            "join_date": data["join_date"],
            "access_start": data["access_start"],
            "access_end": data["access_end"],
        })

        db.commit()

        return {
            "status": 201,
            "message": "Access detail created successfully.",
            "data": data,
        }

    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Insert failed: {str(e)}")

@router.delete("/delete_access_detail/{access_id}", dependencies=[Depends(verify_token)])
def delete_access_detail(access_id: int, db: Session = Depends(get_db)):
    try:
        result = db.execute(
            text("DELETE FROM user_access_details WHERE id = :id"),
            {"id": access_id}
        )

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Access detail not found.")

        db.commit()

        return {
            "status": 200,
            "message": f"Access detail with ID {access_id} deleted successfully."
        }

    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Delete failed.")
