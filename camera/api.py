from fastapi import APIRouter, Depends, HTTPException,status,Query
from sqlalchemy.orm import Session
from DB.db import get_db
from . import service
from . import models

router = APIRouter()


@router.post("/create_camera_type", response_model=models.MessageResponse, 
    status_code=status.HTTP_200_OK
)
def create_camera(camera: models.CameraCreate, db: Session = Depends(get_db)):
    try:
        return service.create_camera(db, camera)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating camera: {str(e)}"
        )


@router.get("/list_camera_type")
def list_cameras(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number (default is 1)")
):
    try:
        return service.list_cameras(db, page)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing cameras: {str(e)}")


@router.get("/{camera_id}")
def get_camera(camera_id: int, db: Session = Depends(get_db)):
    try:
        result = service.get_camera(db, camera_id)
        if not result:
            raise HTTPException(status_code=404, detail="Camera not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching camera: {str(e)}")


@router.put("/{camera_id}")
def update_camera(camera_id: int, title: str, db: Session = Depends(get_db)):
    try:
        result = service.update_camera(db, camera_id, title)
        if not result:
            raise HTTPException(status_code=404, detail="Camera not found or not updated")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating camera: {str(e)}")


@router.delete("/{camera_id}")
def delete_camera(camera_id: int, db: Session = Depends(get_db)):
    try:
        result = service.delete_camera(db, camera_id)
        if not result:
            raise HTTPException(status_code=404, detail="Camera not found or not deleted")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting camera: {str(e)}")
