from fastapi import APIRouter, Depends, HTTPException,Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from fastapi.responses import FileResponse
from DB.db import SessionLocal
from .models import PropertyBuildingCreate,PropertyBuildingOut
from typing import List
from utils.security import verify_token
from DB.db import get_db  
from fastapi import UploadFile, File, Form
from datetime import datetime
import traceback
import os
from common.logger import log
import pandas as pd



router = APIRouter()



# @router.get("/list_building",dependencies=[Depends(verify_token)])
# async def list_buildings(db: Session = Depends(get_db)):
#     try:
#         result = db.execute(text("SELECT * FROM property_building"))
#         rows = result.fetchall()

#         if not rows:
#             raise HTTPException(status_code=404, detail="No buildings found.")

#         data = []
#         for row in rows:
#             data.append({
#                 "id": row[0],
#                 "property_id":row[1],
#                 "building_name": row[2],
#                 "import_file_path":row[3],
#                 "address_number":row[4],
#                 "created_at": row[5],
#                 "updated_at": row[6],
#             })

#         return {
            
#             "data": data,
#             "message": "Buildings retrieved successfully.",
#             "status":200
#         }

#     except HTTPException as http_exc:
#         raise http_exc
#     except Exception as e:
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail="Internal Server Error")
    
@router.get("/list_building_property", dependencies=[Depends(verify_token)])
async def list_buildings(db: Session = Depends(get_db)):
    try:
        log("Building List")
        query = text("""
            SELECT 
                pb.id, pb.property_id, p.title AS property_title,
                pb.building_name, pb.import_file_path, pb.address_number,
                pb.created_at, pb.updated_at
            FROM property_building pb
            LEFT JOIN property p ON pb.property_id = p.id
            ORDER BY pb.id DESC
        """)
        result = db.execute(query)
        rows = result.fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail="No buildings found.")

        data = []
        for row in rows:
            data.append({
                "id": row[0],
                "property_id": row[1],
                "property_title": row[2],
                "building_name": row[3],
                "import_file_path": row[4],
                "address_number": row[5],
                "created_at": row[6],
                "updated_at": row[7],
            })

        return {
            "data": data,
            "message": "Buildings retrieved successfully.",
            "status": 200
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
# @router.post("/create_building", dependencies=[Depends(verify_token)])
# def create_building(building: PropertyBuildingCreate, db: Session = Depends(get_db)):
#     try:
#         query = text("""
#             INSERT INTO property_building 
#             (property_id, building_name, import_file_path, address_number)
#             VALUES 
#             (:property_id, :building_name, :import_file_path, :address_number)
#         """)


#         result = db.execute(query, {
#             "property_id": building.property_id,
#             "building_name": building.building_name,
#             "import_file_path": building.import_file_path,
#             "address_number": building.address_number
#         })
#         db.commit()

#         new_id = result.lastrowid

#         row = db.execute(
#             text("SELECT * FROM property_building WHERE id = :id"),
#             {"id": new_id}
#         ).mappings().fetchone()

#         return {
#             "data": PropertyBuildingOut(**row),
#             "status": 200,
#             "message": "Building created successfully."
#         }

#     except Exception as e:
#         db.rollback()
#         raise HTTPException(status_code=500, detail=f"Insert failed: {e}")

    
# @router.put("/update_building/{building_id}", dependencies=[Depends(verify_token)])
# def update_building(building_id: int, building: PropertyBuildingCreate, db: Session = Depends(get_db)):
#     try:
#         query = text("""
#             UPDATE property_building SET 
#             property_id = :property_id,
#             building_name = :building_name,
#             import_file_path = :import_file_path,
#             address_number = :address_number,
#             updated_at = :updated_at
#             WHERE id = :id
#         """)

#         result = db.execute(query, {
#             "property_id": building.property_id,
#             "building_name": building.building_name,
#             "import_file_path": building.import_file_path,
#             "address_number": building.address_number,
#             "updated_at": datetime.now(),
#             "id": building_id
#         })

#         if result.rowcount == 0:
#             raise HTTPException(status_code=404, detail="Building not found.")

#         db.commit()

#         row = db.execute(
#             text("SELECT * FROM property_building WHERE id = :id"),
#             {"id": building_id}
#         ).mappings().fetchone()

#         return {
#             "status": 200,
#             "data": PropertyBuildingOut(**row),
#             "message": "Building updated successfully."
#         }

#     except HTTPException:
#         raise
#     except Exception as e:
#         db.rollback()
#         raise HTTPException(status_code=500, detail=f"Update failed: {e}")

    
# @router.delete("/delete_building/{building_id}",dependencies=[Depends(verify_token)])
# def delete_building(building_id: int, db: Session = Depends(get_db)):
#     try:
#         result = db.execute(
#             text("DELETE FROM property_building WHERE id = :id"),
#             {"id": building_id}
#         )

#         if result.rowcount == 0:
#             raise HTTPException(status_code=404, detail="Building not found.")

#         db.commit()

#         return {
#             "status":200,
#             "message": f"Building with id {building_id} deleted successfully."
#         }

#     except HTTPException:
#         raise
#     except Exception as e:
#         db.rollback()
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail="Delete failed.")
    
# @router.post("/upload_building_import", dependencies=[Depends(verify_token)])
# async def upload_building_import(
#     building_name: str = Form(...),
#     file: UploadFile = File(...),
#     db: Session = Depends(get_db)
# ):
#     try:
#         if not file.filename.endswith(".xlsx"):
#             raise HTTPException(status_code=400, detail="Only .xlsx files are allowed.")

#         property_id = 1 

#         upload_dir = os.path.join("building_import", str(property_id))
#         os.makedirs(upload_dir, exist_ok=True)

#         timestamp = datetime.now().timestamp()
#         filename = f"{timestamp}_{file.filename}"
#         full_path = os.path.join(upload_dir, filename).replace("\\", "/")  

#         with open(full_path, "wb") as f:
#             f.write(await file.read())

#         insert_query = text("""
#             INSERT INTO property_building (property_id, building_name, import_file_path)
#             VALUES (:property_id, :building_name, :import_file_path)
#         """)
#         db.execute(insert_query, {
#             "property_id": property_id,
#             "building_name": building_name,
#             "import_file_path": full_path
#         })
#         db.commit()

#         return {
#             "status": 200,
#             "message": "Building and file uploaded successfully.",
#             "property_id": property_id,
#             "file_path": full_path
#         }

#     except Exception as e:
#         db.rollback()
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

@router.post("/create_building")
async def upload_building_import(
    building_name: str = Form(None),  
    property_id: int = Form(None),   
    file: UploadFile = File(None),  
    db: Session = Depends(get_db)
):
    try:
        required_fields = {
            "Building Name": building_name,
            "File": file.filename if file else None
        }
        for field, value in required_fields.items():
            if not value:
                raise HTTPException(
                    status_code=400,
                    detail=f"Field '{field}' is required."
                )
            
        existing_building = db.execute(
         text("SELECT id FROM property_building WHERE property_id = :property_id AND building_name = :building_name"),
        {"property_id": property_id, "building_name": building_name}).fetchone()

        if existing_building:
         raise HTTPException(
        status_code=400,
        detail=f"Building name '{building_name}' already exists."
     )
            
        

        log(f"[API Triggered] POST /create_building - property_id={property_id}, building_name={building_name}, file={file.filename}")

        if not file.filename.endswith(".xlsx"):
            raise HTTPException(status_code=400, detail="Only .xlsx files are allowed.")

        upload_dir = os.path.join("building_import", str(property_id))
        os.makedirs(upload_dir, exist_ok=True)

        timestamp = datetime.now().timestamp()
        filename = f"{timestamp}_{file.filename}"
        full_path = os.path.join(upload_dir, filename).replace("\\", "/")

        is_assign = 0

        with open(full_path, "wb") as f:
            f.write(await file.read())

        db.execute(text("""
            INSERT INTO property_building (property_id,is_assign, building_name, import_file_path)
            VALUES (:property_id, :is_assign, :building_name, :import_file_path)
        """), {
            "property_id": property_id,
            "building_name": building_name,
            "import_file_path": full_path,
            "is_assign": is_assign
        })
        building_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()
        db.commit()

        print(f"[LOG] Created building_id: {building_id}")
       

        df = pd.read_excel(full_path)
        required_columns = ["Level", "Area Type", "Unit Start", "Unit End", "Running Number", "Unit Nos"]
        if not all(col in df.columns for col in required_columns):
            raise HTTPException(status_code=400, detail=f"Excel must contain columns: {', '.join(required_columns)}")

        for _, row in df.iterrows():
            level = str(row["Level"]).strip()
            area_type_name = str(row["Area Type"]).strip()
            unit_start = int(row["Unit Start"]) if not pd.isna(row["Unit Start"]) else None
            unit_end = int(row["Unit End"]) if not pd.isna(row["Unit End"]) else None
            running_number_val = str(row["Running Number"]).strip().lower()
            unit_nos = str(row["Unit Nos"]).strip() if not pd.isna(row["Unit Nos"]) else ""

            total_unit = unit_end - unit_start + 1 if unit_start is not None and unit_end is not None else 0
            running_number = 1 if running_number_val == "yes" else 0

            print(f"[ROW] Level: {level}, Area: {area_type_name}, Start: {unit_start}, End: {unit_end}, Running: {running_number}, Units: {unit_nos}")
            log(f"[ROW] Level: {level}, Area: {area_type_name}, Start: {unit_start}, End: {unit_end}, Running: {running_number}, Units: {unit_nos}")

            area_type = db.execute(
                text("SELECT id FROM level_area_type WHERE type_name = :type_name"),
                {"type_name": area_type_name}
            ).fetchone()
            if not area_type:
                raise HTTPException(status_code=400, detail=f"Area type '{area_type_name}' not found.")
            area_type_id = area_type[0]

            db.execute(
                text("""
                    INSERT INTO building_level (
                        building_id, area_type_id, level,
                        total_unit, running_number, start, end,is_assign
                    )
                    VALUES (
                        :building_id, :area_type_id, :level,
                        :total_unit, :running_number, :start, :end,:is_assign
                    )
                """),
                {
                    "building_id": building_id,
                    "area_type_id": area_type_id,
                    "level": level,
                    "total_unit": total_unit,
                    "running_number": running_number,
                    "start": unit_start,
                    "end": unit_end,
                    "is_assign":is_assign
                }
            )
            level_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()

            if unit_nos:
                sorted_units = sorted(
                    [x.strip() for x in unit_nos.split(",") if x.strip()],
                    key=lambda x: int(x) if x.isdigit() else x
                )
                for unit_no in sorted_units:
                    db.execute(
                        text("""
                            INSERT INTO building_units (
                                building_id, level_id, unit_no, unit_name
                            )
                            VALUES (:building_id, :level_id, :unit_no, :unit_name)
                        """),
                        {
                            "building_id": building_id,
                            "level_id": level_id,
                            "unit_no": unit_no,
                            "unit_name": 0
                        }
                    )
            elif running_number == 1 and unit_start is not None and unit_end is not None:
                for unit_no in range(unit_start, unit_end + 1):
                    db.execute(
                        text("""
                            INSERT INTO building_units (
                                building_id, level_id, unit_no, unit_name
                            )
                            VALUES (:building_id, :level_id, :unit_no, :unit_name)
                        """),
                        {
                            "building_id": building_id,
                            "level_id": level_id,
                            "unit_no": str(unit_no),
                            "unit_name": 0
                        }
                    )

        db.commit()

        return {
            "status": 200,
            "message": "Building and levels imported successfully.",
            "property_id": property_id,
            "building_id": building_id,
            "file_path": full_path
        }
    

    except HTTPException:
        log(f"[API Error]")
        raise
    except Exception as e:
        db.rollback()
        error_msg = f"Upload failed: {e}"
        log(f"[API Exception] {error_msg}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")
    
@router.put("/update_building")
async def update_building_import(
    building_id: int = Form(...),
    building_name: str = Form(None),
    property_id: int = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    try:
        existing_building = db.execute(
            text("SELECT building_name, property_id, import_file_path FROM property_building WHERE id = :building_id"),
            {"building_id": building_id}
        ).fetchone()

        if not existing_building:
            raise HTTPException(status_code=404, detail=f"Building ID {building_id} not found.")

        old_building_name, old_property_id, old_file_path = existing_building
        updated_building_name = building_name or old_building_name
        updated_property_id = property_id or old_property_id

        # Duplicate name check
        duplicate_check = db.execute(
            text("SELECT id FROM property_building WHERE property_id = :property_id AND building_name = :building_name AND id != :building_id"),
            {"property_id": updated_property_id, "building_name": updated_building_name, "building_id": building_id}
        ).fetchone()
        if duplicate_check:
            raise HTTPException(status_code=400, detail=f"Building name '{updated_building_name}' already exists for this property.")

        upload_dir = os.path.join("building_import", str(updated_property_id))
        os.makedirs(upload_dir, exist_ok=True)

        if file:
            if not file.filename.endswith(".xlsx"):
                raise HTTPException(status_code=400, detail="Only .xlsx files are allowed.")

            timestamp = datetime.now().timestamp()
            filename = f"{timestamp}_{file.filename}"
            full_path = os.path.join(upload_dir, filename).replace("\\", "/")

            with open(full_path, "wb") as f:
                f.write(await file.read())

            # Read Excel
            df = pd.read_excel(full_path)
            required_columns = ["Level", "Area Type", "Unit Start", "Unit End", "Running Number", "Unit Nos"]
            if not all(col in df.columns for col in required_columns):
                raise HTTPException(status_code=400, detail=f"Excel must contain columns: {', '.join(required_columns)}")

            # ✅ Gather all new units from Excel
            new_units_set = set()
            for _, row in df.iterrows():
                unit_start = int(row["Unit Start"]) if not pd.isna(row["Unit Start"]) else None
                unit_end = int(row["Unit End"]) if not pd.isna(row["Unit End"]) else None
                running_number_val = str(row["Running Number"]).strip().lower()
                unit_nos = str(row["Unit Nos"]).strip() if not pd.isna(row["Unit Nos"]) else ""

                if unit_nos:
                    new_units_set.update([x.strip() for x in unit_nos.split(",") if x.strip()])
                elif running_number_val == "yes" and unit_start is not None and unit_end is not None:
                    new_units_set.update([str(x) for x in range(unit_start, unit_end + 1)])

            # ✅ Get existing assigned units from DB
            assigned_units = db.execute(text("""
                SELECT bu.unit_no
                FROM user_access_details uad
                JOIN building_units bu ON uad.unit_id = bu.id
                WHERE bu.building_id = :building_id
            """), {"building_id": building_id}).scalars().all()

            # Check if any assigned unit is missing in new Excel
            for assigned_unit in assigned_units:
                if str(assigned_unit) not in new_units_set:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Update not allowed: Assigned unit {assigned_unit} is missing in the new Excel sheet."
                    )

            level_ids = db.execute(
                text("SELECT id FROM building_level WHERE building_id = :building_id"),
                {"building_id": building_id}
            ).fetchall()
            for lvl in level_ids:
                db.execute(text("DELETE FROM building_units WHERE level_id = :level_id"), {"level_id": lvl[0]})
            db.execute(text("DELETE FROM building_level WHERE building_id = :building_id"), {"building_id": building_id})

            # Insert new levels + units same as your original logic
            for _, row in df.iterrows():
                level = str(row["Level"]).strip()
                area_type_name = str(row["Area Type"]).strip()
                unit_start = int(row["Unit Start"]) if not pd.isna(row["Unit Start"]) else None
                unit_end = int(row["Unit End"]) if not pd.isna(row["Unit End"]) else None
                running_number_val = str(row["Running Number"]).strip().lower()
                unit_nos = str(row["Unit Nos"]).strip() if not pd.isna(row["Unit Nos"]) else ""
                total_unit = unit_end - unit_start + 1 if unit_start is not None and unit_end is not None else 0
                running_number = 1 if running_number_val == "yes" else 0

                area_type = db.execute(
                    text("SELECT id FROM level_area_type WHERE type_name = :type_name"),
                    {"type_name": area_type_name}
                ).fetchone()
                if not area_type:
                    raise HTTPException(status_code=400, detail=f"Area type '{area_type_name}' not found.")
                area_type_id = area_type[0]

                db.execute(
                    text("""INSERT INTO building_level (
                        building_id, area_type_id, level,
                        total_unit, running_number, start, end, is_assign
                    ) VALUES (
                        :building_id, :area_type_id, :level,
                        :total_unit, :running_number, :start, :end, 0
                    )"""),
                    {
                        "building_id": building_id,
                        "area_type_id": area_type_id,
                        "level": level,
                        "total_unit": total_unit,
                        "running_number": running_number,
                        "start": unit_start,
                        "end": unit_end
                    }
                )
                level_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()

                if unit_nos:
                    for unit_no in [x.strip() for x in unit_nos.split(",") if x.strip()]:
                        db.execute(
                            text("""INSERT INTO building_units (building_id, level_id, unit_no, unit_name)
                                   VALUES (:building_id, :level_id, :unit_no, 0)"""),
                            {"building_id": building_id, "level_id": level_id, "unit_no": unit_no}
                        )
                elif running_number == 1 and unit_start is not None and unit_end is not None:
                    for unit_no in range(unit_start, unit_end + 1):
                        db.execute(
                            text("""INSERT INTO building_units (building_id, level_id, unit_no, unit_name)
                                   VALUES (:building_id, :level_id, :unit_no, 0)"""),
                            {"building_id": building_id, "level_id": level_id, "unit_no": str(unit_no)}
                        )
        else:
            full_path = old_file_path

        db.execute(
            text("UPDATE property_building SET building_name = :building_name, property_id = :property_id, import_file_path = :file_path WHERE id = :building_id"),
            {"building_name": updated_building_name, "property_id": updated_property_id, "file_path": full_path, "building_id": building_id}
        )
        db.commit()

        return {
            "status": 200,
            "message": "Building updated successfully.",
            "building_id": building_id,
            "file_path": full_path
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")



@router.get("/building_file")
def get_building_file(building_id: int = Query(..., description="Building ID"), db: Session = Depends(get_db)):
    try:
        record = db.execute(
            text("SELECT import_file_path FROM property_building WHERE id = :building_id"),
            {"building_id": building_id}
        ).fetchone()

        if not record or not record.import_file_path:
            raise HTTPException(status_code=404, detail="No file found for this building.")

        file_path = record.import_file_path
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found on server.")

        return FileResponse(
            path=file_path,
            filename=os.path.basename(file_path),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

# @router.get("/list_imported_files")
# def list_imported_files():
#     try:
#         folder_path = "samplefile"
#         if not os.path.exists(folder_path):
#             raise HTTPException(status_code=404, detail="Folder not found")

#         files = []
#         for file_name in os.listdir(folder_path):
#             file_path = os.path.join(folder_path, file_name)
#             if os.path.isfile(file_path) and file_name.lower().endswith((".xlsx", ".xls")):
#                 files.append({
#                     "name": file_name,
#                     "path": file_path.replace("\\", "/"),  # For consistency
#                     "size_mb": round(os.path.getsize(file_path) / (1024 * 1024), 2),
#                     "download_url": f"/download_file?file_name={file_name}"
#                 })

#         return {
#             "status": 200,
#             "message": "Imported Excel files retrieved successfully.",
#             "data": files
#         }

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


@router.get("/download_file")
def download_file(file_name: str):
    folder_path = "samplefile"
    file_path = os.path.join(folder_path, file_name)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=file_path,
        filename=file_name,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@router.get("/all_list_building", dependencies=[Depends(verify_token)])
async def list_devices(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number (default is 1)")
):
    try:
        per_page = 10
        offset = (page - 1) * per_page

        count_result = db.execute(text("SELECT COUNT(*) FROM property_building"))
        total_count = count_result.scalar()

        result = db.execute(text(f"SELECT * FROM property_building LIMIT {per_page} OFFSET {offset}"))
        rows = result.fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail="No Building found on this page.")

        data = []
        for row in rows:
            data.append({
                "id": row[0],
                "property_id": row[1],
                "building_name": row[2],
                "import_file_path": row[3],
                "is_assign":row[5]
            })

        return {
            "status": 200,
            "data": data,
            "page": page,
            "per_page": per_page,
            "total":total_count,
            "message": "Building retrieved successfully."
        }

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal Server Error")

    
@router.get("/building_list")
def list_all_building_import_data(
    db: Session = Depends(get_db),
    per_page: int = Query(10, ge=1, alias="per_page"), 
    page: int = Query(1, ge=1),
    building_id: Optional[int] = Query(None)
):
    try:
        log(f"[API Triggered] GET /building_list - building_id={building_id}")
        offset = (page - 1) * per_page

        base_query = """
            SELECT * FROM property_building
            WHERE import_file_path IS NOT NULL AND import_file_path != ''
        """
        count_query = "SELECT COUNT(*) FROM property_building WHERE import_file_path IS NOT NULL AND import_file_path != ''"
        params = {}

        if building_id is not None:
            base_query += " AND id = :building_id"
            count_query += " AND id = :building_id"
            params["building_id"] = building_id

        total_count = db.execute(text(count_query), params).scalar()

        base_query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        params.update({"limit": per_page, "offset": offset})

        building_rows = db.execute(text(base_query), params).fetchall()

        if not building_rows:
            return {
                "status": 200,
                "message": "No imported building data found.",
                "data": {
                    "building": []
                },
                "pagination_details": {
                    "page": page,
                    "per_page": per_page,
                    "total": 0,
                    "last_page": 0
                }
            }

        buildings = []
        for building in building_rows:
            b_id = building.id

            file_path = building.import_file_path
            if os.path.exists(file_path):
                try:
                    df = pd.read_excel(file_path).fillna("")
                    excel_data = df.to_dict(orient="records")
                except Exception as ex:
                    excel_data = []
            else:
                excel_data = []

            level_rows = db.execute(text("""
                SELECT
                    bl.id,
                    bl.level,
                    bl.total_unit,
                    bl.running_number,
                    bl.start,
                    bl.end,
                    bl.is_assign,
                    lat.type_name AS area_type
                FROM building_level bl
                LEFT JOIN level_area_type lat ON bl.area_type_id = lat.id
                WHERE bl.building_id = :building_id
                ORDER BY bl.level ASC
            """), {"building_id": b_id}).fetchall()

            unit_rows = db.execute(text("""
    SELECT
        bu.id,
        bu.unit_no,
        bu.unit_name,
        bu.level_id,
        bu.disabled
    FROM building_units bu
    WHERE bu.building_id = :building_id
    ORDER BY CAST(bu.unit_no AS UNSIGNED)
"""), {"building_id": b_id}).fetchall()


            level_map = {}
            for row in level_rows:
                level_units = [u for u in unit_rows if u.level_id == row.id]
                level_map[row.id] = {
                    "id": row.id,
                    "level": row.level,
                    "area_type": row.area_type,
                    "total_unit": len(level_units),
                    "running_number": row.running_number,
                    "start": row.start,
                    "end": row.end,
                    "is_assign": row.is_assign,
                    "building_unit": []
                }

            for row in unit_rows:
                if row.level_id in level_map:
                    level_map[row.level_id]["building_unit"].append({
                        "id": row.id,
                        "unit_no": row.unit_no,
                        "building_id": b_id,
                        "level_id": row.level_id,
                         "disabled": True if str(row.disabled).lower() in ("1", "true") else False
                    })

            buildings.append({
                "id": building.id,
                "property_id": building.property_id,
                "building_name": building.building_name,
                "is_assign": building.is_assign,
                "import_file_path": building.import_file_path,
                "level": list(level_map.values()),
                "excel_data": excel_data  
            })

        last_page = (total_count + per_page - 1) // per_page  

        return {
            "status": 200,
            "message": "Imported building data listed successfully.",
            "data": {
                "building": buildings
            },
            "pagination_details": {
                "page": page,
                "per_page": per_page,
                "total": total_count,
                "last_page": last_page
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list all building import data: {e}")



    
    
@router.put("/update_building/{building_id}", dependencies=[Depends(verify_token)])
async def update_building_import(
    building_id: int,
    building_name: str = Form(...),
    property_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        log(f"[API Triggered] PUT /update_building - building_id={building_id}")
        if not file.filename.endswith(".xlsx"):
            raise HTTPException(status_code=400, detail="Only .xlsx files are allowed.")

        upload_dir = os.path.join("building_import", str(property_id))
        os.makedirs(upload_dir, exist_ok=True)
        timestamp = datetime.now().timestamp()
        filename = f"{timestamp}_{file.filename}"
        full_path = os.path.join(upload_dir, filename).replace("\\", "/")

        with open(full_path, "wb") as f:
            f.write(await file.read())

        existing = db.execute(
            text("SELECT id FROM property_building WHERE id = :id"),
            {"id": building_id}
        ).fetchone()

        if not existing:
            log(f"Building not found {building_id}")
            raise HTTPException(status_code=404, detail="Building not found.")

        db.execute(
            text("""
                UPDATE property_building
                SET building_name = :building_name, import_file_path = :import_file_path
                WHERE id = :id
            """),
            {
                "building_name": building_name,
                "import_file_path": full_path,
                "id": building_id
            }
        )

        level_ids = db.execute(
            text("SELECT id FROM building_level WHERE building_id = :building_id"),
            {"building_id": building_id}
        ).fetchall()

        if level_ids:
            id_list = [str(row[0]) for row in level_ids]
            id_string = ",".join(id_list)
            db.execute(text(f"DELETE FROM building_units WHERE level_id IN ({id_string})"))
            db.execute(text("DELETE FROM building_level WHERE building_id = :building_id"),
                       {"building_id": building_id})

        df = pd.read_excel(full_path)
        required_columns = ["Level", "Area Type", "Unit Start", "Unit End", "Running Number", "Unit Nos"]
        if not all(col in df.columns for col in required_columns):
            raise HTTPException(status_code=400, detail=f"Excel must contain columns: {', '.join(required_columns)}")

        for _, row in df.iterrows():
            level = str(row["Level"]).strip()
            area_type_name = str(row["Area Type"]).strip()
            unit_start = int(row["Unit Start"]) if not pd.isna(row["Unit Start"]) else None
            unit_end = int(row["Unit End"]) if not pd.isna(row["Unit End"]) else None
            running_number_val = str(row["Running Number"]).strip().lower()
            unit_nos = str(row["Unit Nos"]).strip()

            running_number = 1 if running_number_val == "yes" else 0
            total_unit = (unit_end - unit_start + 1) if running_number and unit_start and unit_end else 0

            area_type = db.execute(
                text("SELECT id FROM level_area_type WHERE type_name = :type_name"),
                {"type_name": area_type_name}
            ).fetchone()
            if not area_type:
                raise HTTPException(status_code=400, detail=f"Area type '{area_type_name}' not found.")
            area_type_id = area_type[0]

            db.execute(
                text("""
                    INSERT INTO building_level (
                        building_id, area_type_id, level,
                        total_unit, running_number, start, end
                    )
                    VALUES (
                        :building_id, :area_type_id, :level,
                        :total_unit, :running_number, :start, :end
                    )
                """),
                {
                    "building_id": building_id,
                    "area_type_id": area_type_id,
                    "level": level,
                    "total_unit": total_unit,
                    "running_number": running_number,
                    "start": unit_start,
                    "end": unit_end
                }
            )
            level_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()

            if running_number and unit_start and unit_end:
                for i in range(unit_start, unit_end + 1):
                    db.execute(
                        text("""
                            INSERT INTO building_units (building_id, level_id, unit_no, unit_name)
                            VALUES (:building_id, :level_id, :unit_no, :unit_name)
                        """),
                        {
                            "building_id": building_id,
                            "level_id": level_id,
                            "unit_no": i,
                            "unit_name": 0
                        }
                    )
            elif unit_nos:
                for unit_no in unit_nos.split(","):
                    unit_no = unit_no.strip()
                    if unit_no:
                        db.execute(
                            text("""
                                INSERT INTO building_units (building_id, level_id, unit_no, unit_name)
                                VALUES (:building_id, :level_id, :unit_no, :unit_name)
                            """),
                            {
                                "building_id": building_id,
                                "level_id": level_id,
                                "unit_no": unit_no,
                                "unit_name": 0
                            }
                        )

        db.commit()

        return {
            "status": 200,
            "message": "Building updated successfully.",
            "property_id": property_id,
            "building_id": building_id,
            "file_path": full_path
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")
    
@router.delete("/delete_building/{building_id}")
def delete_building(building_id: int, db: Session = Depends(get_db)):
    try:
        log(f"[API Triggered] DELETE /delete_building - building_id={building_id}")
        level_rows = db.execute(
            text("SELECT id FROM building_level WHERE building_id = :building_id"),
            {"building_id": building_id}
        ).fetchall()
        level_ids = [row[0] for row in level_rows]

        if not level_ids:
            return {
                "status": 400,
                "message": f"No levels found for building {building_id}. Deletion aborted."
            }
        

        placeholders = ", ".join([str(lid) for lid in level_ids])
        delete_units_sql = f"DELETE FROM building_units WHERE level_id IN ({placeholders})"
        db.execute(text(delete_units_sql))

        db.execute(
            text("DELETE FROM building_level WHERE building_id = :building_id"),
            {"building_id": building_id}
        )

        db.execute(
            text("DELETE FROM property_building WHERE id = :building_id"),
            {"building_id": building_id}
        )

        db.commit()
        return {
            "status": 200,
            "message": f"Building {building_id} and its related data deleted successfully."
        }

    except Exception as e:
        error_msg = f"Delete failed: {e}"
        log(f"[API Exception] {error_msg}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Delete failed: {e}")










