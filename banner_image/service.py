import os
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import UploadFile
import uuid
import shutil

UPLOAD_FOLDER = "banner_images"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)



def delete_old_image(file_path: str):
    """Delete old image file if exists"""
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"Error deleting old image: {str(e)}")

def save_banner_image(file: UploadFile, title: str, image_type: str = "banner") -> str:
    """
    Save banner image to server
    image_type: 'banner' or 'logo'
    """
    try:
        upload_dir = "uploads/banners"
        if image_type == "logo":
            upload_dir = "uploads/logos"
        
        os.makedirs(upload_dir, exist_ok=True)
        
        # Generate unique filename
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{title}_{image_type}_{uuid.uuid4().hex}{file_extension}"
        file_path = os.path.join(upload_dir, unique_filename)
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        return file_path
    except Exception as e:
        raise Exception(f"Failed to save image: {str(e)}")


def create_or_update_banner(
    db: Session, 
    title: str = None, 
    image_path: str = None,
    logo_image_path: str = None
):
    """Create or update banner with both banner image and logo image"""
    existing = db.execute(
        text("SELECT * FROM banner_image LIMIT 1")
    ).mappings().first()

    if existing:
        # Use new values if provided, otherwise keep existing
        new_title = title if title else existing["title"]
        new_image = image_path if image_path is not None else existing["image"]
        new_logo_image = logo_image_path if logo_image_path is not None else existing["logo_image"]

        # Delete old banner image if replaced
        if image_path and existing["image"] and os.path.exists(existing["image"]) and existing["image"] != image_path:
            delete_old_image(existing["image"])

        # Delete old logo image if replaced
        if logo_image_path and existing["logo_image"] and os.path.exists(existing["logo_image"]) and existing["logo_image"] != logo_image_path:
            delete_old_image(existing["logo_image"])

        db.execute(
            text("""
                UPDATE banner_image
                SET title = :title,
                    image = :image,
                    logo_image = :logo_image,
                    updated_at = NOW()
                WHERE id = :id
            """),
            {
                "title": new_title, 
                "image": new_image, 
                "logo_image": new_logo_image,
                "id": existing["id"]
            }
        )
        db.commit()

        result = db.execute(
            text("SELECT * FROM banner_image WHERE id = :id"),
            {"id": existing["id"]}
        ).mappings().first()
    else:
        # Insert new record
        new_title = title if title else "default"
        new_image = image_path if image_path else ""
        new_logo_image = logo_image_path if logo_image_path else ""

        db.execute(
            text("""
                INSERT INTO banner_image (title, image, logo_image) 
                VALUES (:title, :image, :logo_image)
            """),
            {"title": new_title, "image": new_image, "logo_image": new_logo_image}
        )
        db.commit()
        
        result = db.execute(
            text("SELECT * FROM banner_image ORDER BY id DESC LIMIT 1")
        ).mappings().first()

    return result

def list_banners(db: Session, page: int = 1, per_page: int = 10):
    offset = (page - 1) * per_page
    banners = db.execute(
        text("""
            SELECT * FROM banner_image
            ORDER BY id DESC
            LIMIT :limit OFFSET :offset
        """), {"limit": per_page, "offset": offset}
    ).mappings().all()
    return banners
