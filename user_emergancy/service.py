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

@router.get("/list_emergency_contacts", dependencies=[Depends(verify_token)])
async def list_emergency_contacts(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1)
):
    try:
        per_page = 10
        offset = (page - 1) * per_page

        total = db.execute(text("SELECT COUNT(*) FROM user_emergency")).scalar()
        result = db.execute(text(f"SELECT * FROM user_emergency LIMIT {per_page} OFFSET {offset}"))
        rows = result.fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail="No emergency contacts found.")

        data = []
        for row in rows:
            data.append({
                "id": row[0],
                "first_name": row[1],
                "last_name": row[2],
                "email": row[3],
                "phone": row[4],
                "country_code": row[5],
                "nationality": row[6],
                "gender": row[7],
                "relationship": row[8],
            })

        return {
            "status": 200,
            "data": data,
            "page": page,
            "per_page": per_page,
            "total": total,
            "message": "Emergency contacts retrieved successfully."
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.post("/create_emergency_contact", dependencies=[Depends(verify_token)])
async def create_emergency_contact(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()

        query = text("""
            INSERT INTO user_emergency 
            (first_name, last_name, email, phone, country_code, nationality, gender, relationship)
            VALUES 
            (:first_name, :last_name, :email, :phone, :country_code, :nationality, :gender, :relationship)
        """)

        db.execute(query, {
            "first_name": data["first_name"],
            "last_name": data.get("last_name"),
            "email": data.get("email"),
            "phone": data.get("phone"),
            "country_code": data.get("country_code"),
            "nationality": data.get("nationality"),
            "gender": data.get("gender"),
            "relationship": data.get("relationship"),
        })

        db.commit()

        return {
            "status": 201,
            "message": "Emergency contact created successfully.",
            "data": data,
        }

    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Insert failed: {str(e)}")

@router.delete("/delete_emergency_contact/{contact_id}", dependencies=[Depends(verify_token)])
def delete_emergency_contact(contact_id: int, db: Session = Depends(get_db)):
    try:
        result = db.execute(
            text("DELETE FROM user_emergency WHERE id = :id"),
            {"id": contact_id}
        )

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Emergency contact not found.")

        db.commit()

        return {
            "status": 200,
            "message": f"Emergency contact with ID {contact_id} deleted successfully."
        }

    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Delete failed.")
