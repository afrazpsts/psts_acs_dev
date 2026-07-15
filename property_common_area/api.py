from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from DB.db import get_db
from .models import PropertyCommonAreaCreate
from utils.security import verify_token
from .service import (
    list_property_common_areas_service,
    create_property_common_area_service
)


router = APIRouter()


@router.get("/list_property_common_area", dependencies=[Depends(verify_token)])
def list_property_common_areas(db: Session = Depends(get_db)):
    results = list_property_common_areas_service(db)
    return {
        "status": 200,
        "message": "Property common areas retrieved successfully.",
        "data": results
    }



@router.post("/create_property_common_area", dependencies=[Depends(verify_token)])
def create_property_common_area(payload: PropertyCommonAreaCreate, db: Session = Depends(get_db)):
    result = create_property_common_area_service(payload.dict(), db)
    return {
        "status": 201,
        "message": "Property common area created successfully.",
        "data": result
    }
