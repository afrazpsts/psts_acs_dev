from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException

# def list_property_common_areas_service(db: Session):
#     try:
#         query = db.execute(text("""
#             SELECT 
#                 pca.*,
#                 p.title AS property_title,
#                 pb.building_name,
#                 bl.level
#             FROM property_common_area pca
#             LEFT JOIN property p ON pca.property_id = p.id
#             LEFT JOIN property_building pb ON pca.building_id = pb.id
#             LEFT JOIN building_level bl ON pca.level_id = bl.id
#             ORDER BY pca.id DESC
#         """)).mappings().all()

#         buildings_dict = {}
#         common_areas_without_building = []

#         for row in query:
#             if row["building_id"] and row["level_id"]:  
#                 b_id = row["building_id"]
#                 if b_id not in buildings_dict:
#                     buildings_dict[b_id] = {
#                         "building_id": b_id,
#                         "building_name": row["building_name"],
#                         "level_id": row["level_id"],
#                         "level": row["level"],
#                         "property_title": row["property_title"],
#                         "common_areas": []
#                     }
#                 buildings_dict[b_id]["common_areas"].append({
#                     "id": row["id"],
#                     "common_area_name": row["common_area_name"],
#                     "description": row["description"],
#                 })
#             else:  
#                 common_areas_without_building.append({
#                     "id": row["id"],
#                     "common_area_name": row["common_area_name"],
#                     "description": row["description"],
#                     "property_title": row["property_title"]
#                 })

#         return {
#             "buildings": list(buildings_dict.values()),
#             "common_areas_without_building": common_areas_without_building
#         }

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
    

def list_property_common_areas_service(db: Session):
    try:
        query = db.execute(text("""
            SELECT 
                pca.*,
                p.title AS property_title,
                pb.building_name,
                bl.level
            FROM property_common_area pca
            LEFT JOIN property p ON pca.property_id = p.id
            LEFT JOIN property_building pb ON pca.building_id = pb.id
            LEFT JOIN building_level bl ON pca.level_id = bl.id
            ORDER BY pca.id DESC
        """)).mappings().all()

        merged_list = []

        for row in query:
            merged_list.append({
                "id": row["id"],
                "common_area_name": row["common_area_name"],
                "description": row["description"],
                "property_title": row["property_title"],
                "building_id": row["building_id"],
                "building_name": row["building_name"],
                "level_id": row["level_id"],
                "level": row["level"]
            })

        return merged_list

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



def create_property_common_area_service(data: dict, db: Session):
    try:
        insert_sql = text("""
            INSERT INTO property_common_area 
            (common_area_name, description, is_part_of_building, property_id, building_id, level_id, created_at)
            VALUES (:common_area_name, :description, :is_part_of_building, :property_id, :building_id, :level_id, NOW())
        """)
        db.execute(insert_sql, data)
        db.commit()

        last_id = db.execute(text("SELECT LAST_INSERT_ID() AS id")).scalar()

        result = db.execute(
            text("""
                SELECT 
                    pca.*,
                    p.title,
                    pb.building_name,
                    bl.level
                FROM property_common_area pca
                LEFT JOIN property p ON pca.property_id = p.id
                LEFT JOIN property_building pb ON pca.building_id = pb.id
                LEFT JOIN building_level bl ON pca.level_id = bl.id
                WHERE pca.id = :id
            """),
            {"id": last_id}
        ).mappings().first()

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
