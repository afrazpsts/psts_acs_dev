from fastapi import APIRouter, Depends, HTTPException,Form,File,UploadFile
from sqlalchemy.orm import Session
from .models import AddPersonRequest
from .service import add_person_to_device, store_person_in_db
from utils.security import verify_token
from DB.db import get_db

router = APIRouter()

@router.post("/add_person", dependencies=[Depends(verify_token)])
def add_person_api(payload: AddPersonRequest, db: Session = Depends(get_db)):
    device_result = add_person_to_device(payload)

    if device_result["status"] != "success":
        raise HTTPException(status_code=500, detail=device_result.get("message") or device_result.get("error"))

    db_result = store_person_in_db(db, payload)

    if db_result["status"] != "success":
        raise HTTPException(status_code=500, detail=f"Device OK but DB insert failed: {db_result['message']}")

    return {
        "status": 200,
        "message": "Person added to device and stored in database",
        "data": device_result["data"]
    }




# @router.post("/upload_face", dependencies=[Depends(verify_token)])
# def upload_face(
#     employee_no: str = Form(...),
#     img: UploadFile = File(...),
#     db: Session = Depends(get_db)
# ):
#     try:
#         result = upload_face_service(db=db, employee_no=employee_no, img=img)
#         return {
#             "status": 200,
#             "message": "Face uploaded successfully",
#             "data": result
#         }
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Face upload failed: {str(e)}")
