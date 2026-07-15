from fastapi import APIRouter, Depends, HTTPException,Request
from sqlalchemy import text
from sqlalchemy.orm import Session
from DB.db import SessionLocal
import traceback
from datetime import datetime
from utils.security import encrypt_password, decrypt_password
from utils.security import verify_token
from fastapi import Query



router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/list_resident_type", dependencies=[Depends(verify_token)])
async def list_resident_type(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number (default is 1)")
):
    try:
        per_page = 10
        offset = (page - 1) * per_page

        count_result = db.execute(text("SELECT COUNT(*) FROM  residency_type"))
        total_count = count_result.scalar()

        result = db.execute(text(f"SELECT * FROM  residency_type LIMIT {per_page} OFFSET {offset}"))
        rows = result.fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail="No resident type found on this page.")

        data = []
        for row in rows:
            data.append({
                "id": row[0],
                "key": row[1],
                "name": row[2],
                "is_employee": row[3],
                "description": row[4],
            })

        return {
            "status": 200,
            "data": data,
            "page": page,
            "per_page": per_page,
            "total":total_count,
            "message": "Resident Type retrieved successfully."
        }

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/create_resident_type",dependencies=[Depends(verify_token)])
async def create_device(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()


        query = text("""
            INSERT INTO resident residency_type_type 
            (key, name, is_employee, description, created_date, updated_date)
            VALUES 
            (:key, :name, :is_employee, :description, :created_date, :updated_date)
        """)

        db.execute(query, {
            "key": data["key"],
            "name": data["name"],
            "is_employee": data.get("is_employee"),
            "description": data["description"],
            "created_date": datetime.now(),
            "updated_date": datetime.now()
        })
        db.commit()
        
        return {
            "status":201,
            "message": "Resident Type created successfully.",
            "data": data,
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Insert failed: {str(e)}")
    
# @router.put("/update_device/{device_id}", dependencies=[Depends(verify_token)])
# async def update_device(device_id: int, request: Request, db: Session = Depends(get_db)):
#     try:
#         data = await request.json()

#         hashed_password = None
#         if "password" in data and data["password"]:
#            encrypted_password = encrypt_password(data["password"])


#         update_query = text("""
#             UPDATE camera_devices
#             SET name = :name,
#                 ip = :ip,
#                 user_name = :user_name,
#                 type = :type,
#                 port = :port,
#                 password = COALESCE(:password, password),
#                 updated_date = :updated_date
#             WHERE id = :device_id
#         """)

#         db.execute(update_query, {
#             "device_id": device_id,
#             "name": data["name"],
#             "ip": data["ip"],
#             "user_name": data.get("user_name"),
#             "type": data["type"],
#             "port": data["port"],
#             "password": hashed_password,
#             "updated_date": datetime.now()
#         })

#         db.commit()
#         return {"message": "Device updated successfully."}

#     except Exception as e:
#         db.rollback()
#         raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")

    

    
@router.delete("/delete_resident_type/{resident_type_id}",dependencies=[Depends(verify_token)])
def delete_building(resident_type_id: int, db: Session = Depends(get_db)):
    try:
        result = db.execute(
            text("DELETE FROM  residency_type WHERE id = :id"),
            {"id": resident_type_id}
        )

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail=" resident_type not found.")

        db.commit()

        return {
            "status":200,
            "message": f"resident type with id {resident_type_id} deleted successfully."
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Delete failed.")
