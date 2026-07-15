from fastapi import FastAPI , HTTPException , APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.orm import Session
from DB.db import SessionLocal
from utils.security import verify_token
from DB.db import get_db
from .models import BlockBuildingCreate,BlockBuildingOut
from common.logger import log
import traceback


router = APIRouter()


@router.post("/create_block_building",dependencies=[Depends(verify_token)])
def create_block_building(block_building:BlockBuildingCreate,db:Session = Depends(get_db)):
    try:
        insert_query =text(""" INSERT into block_building (building_id , block_id)
                            VALUES(:building_id,:block_id)""")
        
        result = db.execute(insert_query,{
            "building_id":block_building.building_id,
            "block_id":block_building.block_id
        })

        db.commit()

        new_id = result.lastrowid

        row = db.execute(
            text("""
        SELECT id, building_id, block_id,created_at,updated_at from block_building WHERE id = :id"""), {"id": new_id}
        ).mappings().fetchone()

        return {
            "data": BlockBuildingOut
            (**row),
            "status": 200,
            "message": "Block Building Created Successfully."
        }

    except Exception as e:
        db.rollback()
        error_msg = f"Insert failed: {e}"
        log(f"[API Exception] {error_msg}")
        raise HTTPException(status_code=500, detail=f"Insert failed: {e}")  
    
@router.put("/update_block_building/{block_building_id}", dependencies=[Depends(verify_token)])
def update_block(block_building_id: int, blockbuilding: BlockBuildingCreate, db: Session = Depends(get_db)):
    try:
        log(f"[API Triggered] PUT /update_block - block_building_id={block_building_id}")
        existing = db.execute(
            text("SELECT * FROM block_building WHERE id = :id"),
            {"id": block_building_id}
        ).fetchone()

        if not existing:
            raise HTTPException(status_code=404, detail="Block Building Not found")

        update_query = text("""
            UPDATE block_building
            SET building_id = :building_id,
                block_id = :block_id,
                updated_at = NOW()
            WHERE id = :id
        """)
        db.execute(update_query, {
            "building_id": blockbuilding.building_id,
            "block_id": blockbuilding.block_id,
            "id": block_building_id
        })
        db.commit()

        row = db.execute(
            text("""
                SELECT 
                    id,
                    building_id AS building_id,
                    block_id,
                    created_at,
                    updated_at
                FROM block_building
                WHERE id = :id
            """),
            {"id": block_building_id}
        ).mappings().fetchone()

        return {
            "data": BlockBuildingOut(**row),
            "status": 200,
            "message": "Block Building updated successfully."
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")
    
@router.get("/list_block_building/{block_building_id}", dependencies=[Depends(verify_token)])
def list_block_building(block_building_id: int, db: Session = Depends(get_db)):
    try:
        log(f"[API Triggered] GET /list_block_building - block_building_id={block_building_id}")
        result = db.execute(text("""
            SELECT 
                bb.id AS block_building_id,
                bb.block_id,
                bb.building_id,
                bb.created_at,
                bb.updated_at,
                pb.building_name
            FROM block_building bb
            JOIN property_building pb ON bb.building_id = pb.id
            WHERE bb.id = :id
        """), {"id": block_building_id}).mappings().fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Block Building relation not found")

        return {
            "status": 200,
            "data": dict(result),
            "message": "Block Building details retrieved successfully"
        }

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        traceback.print_exc()
        error_msg = f"Internal Server Error: {e}"
        log(f"[API Exception] {error_msg}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
@router.delete("/delete_block_building/{block_building_id}",dependencies=[Depends(verify_token)])
def delete_block_building(block_building_id:int, db: Session=Depends(get_db)):
    try:
        result = db.execute(text("SELECT * FROM block_building where id = :id"), {"id": block_building_id}).fetchone()
        if not result:
            log("Block Building Not Found")
            raise HTTPException(status_code=404, detail="Block Building Not found")
        
        db.execute(text("DELETE FROM block WHERE id = :id"), {"id": block_building_id})
        db.commit()
        return {"status": 200, "message": "Block deleted successfully"}
    except HTTPException :
        raise
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        error_msg = f"Deleted Failed: {e}"
        log(f"[API Exception] {error_msg}")
        raise HTTPException(status_code=500,detail="Deleted Failed")