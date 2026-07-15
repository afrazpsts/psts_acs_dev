from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form,Query
from sqlalchemy.orm import Session
from DB.db import get_db
from utils.security import verify_token
from . import service
from common.logger import log
from sqlalchemy import text
import traceback
from .model import RoleMenuPermissionRequest




router = APIRouter()

@router.post("/create_menu")
async def create_menu(
    name: str = Form(...),
    key: str = Form(...),
    description: str = Form(None),
    navigation: str = Form(None),
    menu_for: int = Form(...),
    is_submenu: int = Form(0),
    parent_menu_id: str = Form(None),
    allowed_user_role: str = Form(None),
    allowed_department: str = Form(None),
    service_id: str = Form(None),
    access_ids: str = Form(None),
    sort_order: str = Form(None),
    icon: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    try:
        return await service.create_menu(
            name, key, description, navigation, menu_for, is_submenu,
            parent_menu_id, allowed_user_role, allowed_department,
            service_id, access_ids, sort_order, icon, db
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Insert failed: {str(e)}")


@router.get("/menu_list", dependencies=[Depends(verify_token)])
def get_menu_list(
    user_role: int = Query(..., description="User role ID"),
    db: Session = Depends(get_db)
):
    try:
        log(f"API trigger GET /menu_list for user_role={user_role}")
        return service.get_menu_list(db, user_role)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Menu fetch failed: {str(e)}")
    
@router.get("/list_image_banners")
async def list_image_banners(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100)
):
    try:
        offset = (page - 1) * per_page
        query = text("""
            SELECT 
                id,title, image, created_at, updated_at, logo_image
            FROM banner_image
            ORDER BY id DESC
            LIMIT :limit OFFSET :offset
        """)
        result = db.execute(query, {"limit": per_page, "offset": offset})
        rows = result.fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail="No banners found.")

        data = []
        for row in rows:
         data.append({
        "id": row[0],
        "title": row[1],
        "image_path": row[2].replace("\\", "/"),  
        "created_at": row[3],
        "updated_at": row[4],
         "logo_image_path": row[5].replace("\\", "/") if row[5] else None,
    })


        return {
            "data": data,
            "message": "Banners retrieved successfully.",
            "status": 200
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.post("/set_role_menu_permission")
def set_role_menu_permission(
    request: RoleMenuPermissionRequest,
    db: Session = Depends(get_db)
):
    return service.set_role_menu_permission(
        request.role_id, 
        request.menu_ids, 
        request.enabled, 
        db
    )