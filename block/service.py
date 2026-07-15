from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.orm import Session
from DB.db import SessionLocal
from .models import BlockCreate,BlockOut
from typing import List
from utils.security import verify_token
from DB.db import get_db  
import traceback
from fastapi import Query
from common.logger import log
import json


router = APIRouter()

# @router.post("/create_block", response_model=BlockOut)
# def create_block(block: BlockCreate, db: Session = Depends(get_db)):
#     query = text("""
#         INSERT INTO block (Name, description)
#         VALUES (:name, :description)
#     """)
#     db.execute(query, {
#         "name": block.name,
#         "description": block.description
#     })
#     db.commit()

#     result = db.execute(text("SELECT * FROM block ORDER BY id DESC LIMIT 1")).fetchone()
#     if not result:
#         raise HTTPException(status_code=500, detail="Block creation failed")
#     return dict(result)

@router.post("/create_block", dependencies=[Depends(verify_token)])
def create_block(block: BlockCreate, db: Session = Depends(get_db)):
    try:
        log("[API Trigger /create_block POST]")

        new_id = None
        building_ids = []

        if block.block_type == "1":
            insert_query = text("""
                INSERT INTO block (Name, description, block_type, level_ids)
                VALUES (:name, :description, :block_type, :level_ids)
            """)
            result = db.execute(insert_query, {
                "name": block.name,
                "description": block.description,
                "block_type": block.block_type,
                "level_ids": json.dumps(block.level_ids)
            })
            new_id = result.lastrowid

            if block.level_ids:
                db.execute(
                    text("UPDATE building_level SET is_assign = 1 WHERE id IN :ids"),
                    {"ids": tuple(block.level_ids)}
                )

                building_ids_result = db.execute(
                    text("SELECT DISTINCT building_id FROM building_level WHERE id IN :ids"),
                    {"ids": tuple(block.level_ids)}
                ).fetchall()
                building_ids = [row.building_id for row in building_ids_result]

                if building_ids:
                    db.execute(
                        text("UPDATE property_building SET is_assign = 1 WHERE id IN :building_ids"),
                        {"building_ids": tuple(building_ids)}
                    )

        elif block.block_type == "2":
            insert_query = text("""
                INSERT INTO block (Name, description, block_type, level_ids, building_ids)
                VALUES (:name, :description, :block_type, :level_ids,:building_ids)
            """)
            result = db.execute(insert_query, {
                "name": block.name,
                "description": block.description,
                "block_type": block.block_type,
                "level_ids": json.dumps([]),
                "building_ids": json.dumps(block.building_ids or [])
            })
            new_id = result.lastrowid

            if block.building_ids:
                db.execute(
                    text("UPDATE property_building SET is_assign = 1 WHERE id IN :building_ids"),
                    {"building_ids": tuple(block.building_ids)}
                )
                building_ids = block.building_ids

        else:
            raise HTTPException(status_code=400, detail="Invalid block_type")

        db.commit()

        row = db.execute(
            text("""
                SELECT id, Name AS name, description, block_type, level_ids, building_ids,created_at, updated_at
                FROM block
                WHERE id = :id
            """),
            {"id": new_id}
        ).mappings().fetchone()

        row_dict = dict(row)
        row_dict["level_ids"] = json.loads(row_dict["level_ids"]) if row_dict["level_ids"] else []
        row_dict["building_ids"] = json.loads(row_dict["building_ids"]) if row_dict.get("building_ids") else []

        return {
            "data": BlockOut(**row_dict),
            "status": 200,
            "message": "Block created successfully."
        }

    except Exception as e:
        db.rollback()
        log(f"[API Exception] Insert failed: {e}")
        raise HTTPException(status_code=500, detail=f"Insert failed: {e}")


@router.get("/list_blocks")
def list_blocks(db: Session = Depends(get_db)):
    try:
        result = db.execute(text("""
            SELECT 
                b.id, b.Name, b.block_type, b.description, b.created_at, b.updated_at,
                b.level_ids
            FROM block b
        """))
        rows = result.mappings().fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail="No Block found")

        data = []
        for row in rows:
            level_ids = json.loads(row["level_ids"] or "[]")
            level_rows = []
            if level_ids:
                query = text("""
                    SELECT id, level, is_assign 
                    FROM building_level 
                    WHERE id IN :ids
                """)
                res = db.execute(query, {"ids": tuple(level_ids)}).mappings().fetchall()
                level_rows = [
                    {"id": r["id"], "name": r["level"], "is_assign": r["is_assign"]}
                    for r in res
                ]

            data.append({
                "id": row["id"],
                "name": row["Name"],
                "block_type": row["block_type"],
                "description": row["description"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "levels": level_rows 
            })

        return {
            "status": 200,
            "message": "Blocks listed successfully",
            "data": data
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.put("/update_block/{block_id}", dependencies=[Depends(verify_token)])
def update_block(block_id: int, block: BlockCreate, db: Session = Depends(get_db)):
    try:
        log(f"[API Trigger /update_block PUT] block_id={block_id}")

        existing = db.execute(
            text("SELECT * FROM block WHERE id = :id"),
            {"id": block_id}
        ).fetchone()

        if not existing:
            raise HTTPException(status_code=404, detail="Block not found")

        building_ids = []

        if block.block_type == "1":
            db.execute(
                text("""
                    UPDATE block
                    SET Name = :name,
                        description = :description,
                        block_type = :block_type,
                        level_ids = :level_ids,
                        building_ids = NULL,
                        updated_at = NOW()
                    WHERE id = :id
                """),
                {
                    "name": block.name,
                    "description": block.description,
                    "block_type": block.block_type,
                    "level_ids": json.dumps(block.level_ids or []),
                    "id": block_id
                }
            )

            if block.level_ids:
                db.execute(
                    text("UPDATE building_level SET is_assign = 1 WHERE id IN :ids"),
                    {"ids": tuple(block.level_ids)}
                )

                building_ids_result = db.execute(
                    text("SELECT DISTINCT building_id FROM building_level WHERE id IN :ids"),
                    {"ids": tuple(block.level_ids)}
                ).fetchall()
                building_ids = [row.building_id for row in building_ids_result]

                if building_ids:
                    db.execute(
                        text("UPDATE property_building SET is_assign = 1 WHERE id IN :building_ids"),
                        {"building_ids": tuple(building_ids)}
                    )

        elif block.block_type == "2":
            db.execute(
                text("""
                    UPDATE block
                    SET Name = :name,
                        description = :description,
                        block_type = :block_type,
                        level_ids = :level_ids,
                        building_ids = :building_ids,
                        updated_at = NOW()
                    WHERE id = :id
                """),
                {
                    "name": block.name,
                    "description": block.description,
                    "block_type": block.block_type,
                    "level_ids": json.dumps([]),
                    "building_ids": json.dumps(block.building_ids or []),
                    "id": block_id
                }
            )

            if block.building_ids:
                db.execute(
                    text("UPDATE property_building SET is_assign = 1 WHERE id IN :building_ids"),
                    {"building_ids": tuple(block.building_ids)}
                )
                building_ids = block.building_ids

        else:
            raise HTTPException(status_code=400, detail="Invalid block_type")

        db.commit()

        row = db.execute(
            text("""
                SELECT id, Name AS name, description, block_type, level_ids, building_ids, created_at, updated_at
                FROM block
                WHERE id = :id
            """),
            {"id": block_id}
        ).mappings().fetchone()

        row_dict = dict(row)
        row_dict["level_ids"] = json.loads(row_dict["level_ids"]) if row_dict["level_ids"] else []
        row_dict["building_ids"] = json.loads(row_dict["building_ids"]) if row_dict.get("building_ids") else []

        return {
            "data": BlockOut(**row_dict),
            "status": 200,
            "message": "Block updated successfully."
        }

    except Exception as e:
        db.rollback()
        log(f"[API Exception] Update failed: {e}")
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")



# @router.get("/list_block/{block_id}", response_model=BlockOut)
# def get_block(block_id: int, db: Session = Depends(get_db)):
#     result = db.execute(text("SELECT * FROM block WHERE id = :id"), {"id": block_id}).fetchone()
#     if not result:
#         raise HTTPException(status_code=404, detail="Block not found")
#     return dict(result)

@router.delete("/delete_block/{block_id}",dependencies=[Depends(verify_token)])
def delete_block(block_id: int, db: Session = Depends(get_db)):
    try:
      log(f"[API Triggered] DELETE /delete_block - property_id={block_id}")
      result = db.execute(text("SELECT * FROM block WHERE id = :id"), {"id": block_id}).fetchone()
      if not result:
        raise HTTPException(status_code=404, detail="Block not found")

      db.execute(text("DELETE FROM block WHERE id = :id"), {"id": block_id})
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
