from sqlalchemy import text
from sqlalchemy.orm import Session

def create_camera(db: Session, camera):
    query = text("""
        INSERT INTO camera_type (title, created_at, updated_at)
        VALUES (:title, NOW(), NOW())
    """)
    db.execute(query, {"title": camera.title})
    db.commit()
    return {"message": "Camera created successfully"}

def list_cameras(db: Session, page: int):
    per_page = 10
    offset = (page - 1) * per_page

    count_query = text("SELECT COUNT(*) FROM camera_type")
    total_count = db.execute(count_query).scalar()

    query = text("""
        SELECT id, title, created_at, updated_at
        FROM camera_type
        ORDER BY id DESC
        LIMIT :limit OFFSET :offset
    """)
    result = db.execute(query, {"limit": per_page, "offset": offset}).mappings().all()

    if not result:
        return {
            "status": 404,
            "data": [],
            "page": page,
            "per_page": per_page,
            "total": total_count,
            "message": "No cameras found on this page."
        }

    return {
        "status": 200,
        "data": [dict(row) for row in result],
        "page": page,
        "per_page": per_page,
        "total": total_count,
        "message": "Cameras retrieved successfully."
    }

def get_camera(db: Session, camera_id: int):
    query = text("""
        SELECT id, title, created_at, updated_at
        FROM camera_type
        WHERE id = :camera_id
    """)
    result = db.execute(query, {"camera_id": camera_id}).mappings().first()
    return dict(result) if result else None

def update_camera(db: Session, camera_id: int, title: str):
    query = text("""
        UPDATE camera_type
        SET title = :title, updated_at = NOW()
        WHERE id = :camera_id
    """)
    result = db.execute(query, {"title": title, "camera_id": camera_id})
    db.commit()
    return {"message": "Camera updated successfully"} if result.rowcount else None

def delete_camera(db: Session, camera_id: int):
    query = text("DELETE FROM camera_type WHERE id = :camera_id")
    result = db.execute(query, {"camera_id": camera_id})
    db.commit()
    return {"message": "Camera deleted successfully"} if result.rowcount else None
