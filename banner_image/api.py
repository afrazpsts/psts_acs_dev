from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from typing import List
from DB.db import get_db
from .models import BannerImageResponse
from .service import save_banner_image, create_or_update_banner, list_banners as list_banners_crud
from sqlalchemy import text

router = APIRouter()

@router.post("/create_banner", response_model=BannerImageResponse)
def create_banner(
    title: str = Form(None),
    image: UploadFile = File(None),
    logo_image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    """
    Create or update banner with banner image and logo image
    - title: Banner title (optional)
    - image: Banner image file (optional)
    - logo_image: Logo image file (optional)
    """
    try:
        image_path = None
        logo_image_path = None

        # Handle banner image upload
        if image and hasattr(image, "filename") and image.filename:
            existing = db.execute(text("SELECT * FROM banner_image LIMIT 1")).mappings().first()
            effective_title = title or (existing["title"] if existing else "default")
            image_path = save_banner_image(image, effective_title, image_type="banner")

        # Handle logo image upload
        if logo_image and hasattr(logo_image, "filename") and logo_image.filename:
            existing = db.execute(text("SELECT * FROM banner_image LIMIT 1")).mappings().first()
            effective_title = title or (existing["title"] if existing else "default")
            logo_image_path = save_banner_image(logo_image, effective_title, image_type="logo")

        # Update or create banner record
        result = create_or_update_banner(db, title, image_path, logo_image_path)
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




