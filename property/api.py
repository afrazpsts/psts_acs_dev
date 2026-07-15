from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from DB.db import get_db
from utils.security import verify_token
from .model import PropertyCreate, PropertyOut
from . import service

router = APIRouter()

@router.post("/create_property", response_model=PropertyOut, dependencies=[Depends(verify_token)])
async def create_property(property: PropertyCreate, db: Session = Depends(get_db)):
    try:
        return await service.create_property(property, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating property: {str(e)}")

@router.get("/list_properties", response_model=list[PropertyOut], dependencies=[Depends(verify_token)])
def list_properties(db: Session = Depends(get_db)):
    try:
        return service.list_properties(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing properties: {str(e)}")

@router.delete("/delete_property/{property_id}", dependencies=[Depends(verify_token)])
def delete_property(property_id: int, db: Session = Depends(get_db)):
    try:
        return service.delete_property(property_id, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting property: {str(e)}")
