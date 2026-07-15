from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session
from common.logger import log as write_to_server_log
from typing import Optional


from DB.db import SessionLocal


def initialize_roles_table():
    db = SessionLocal()
    try:
        result = db.execute(text("SELECT COUNT(*) FROM roles"))
        count = result.scalar()

        if count == 0:
            db.execute(
                text(
                    """
                    INSERT INTO roles (id, title)
                    VALUES (:id, :title)
                    """
                ),
                {"id": 1, "title": "Super Admin"},
            )
            db.commit()
            print("Default role (Super Admin) created successfully.")
        else:
            print("Roles table already has data. Skipping insert.")
    except ProgrammingError as e:
        print("SQL Error:", e)
    finally:
        db.close()


def create_role_service(title: str, db: Session):
    """
    Service function to create a new role
    Handles duplicate entry errors gracefully
    """
    try:
        if not title:
            raise Exception("Role title is required")
        
        existing_role = db.execute(
            text("SELECT id, title FROM roles WHERE title = :title"),
            {"title": title}
        ).first()
        
        if existing_role:
            raise Exception(f"Role with title '{title}' already exists")
        
        db.execute(
            text("""
                INSERT INTO roles (title, created_at, updated_at)
                VALUES (:title, NOW(), NOW())
            """),
            {"title": title}
        )
        db.commit()
        
        created = db.execute(
            text("SELECT * FROM roles WHERE title = :title"),
            {"title": title}
        ).mappings().first()
        
        if not created:
            created = db.execute(
                text("SELECT * FROM roles ORDER BY id DESC LIMIT 1")
            ).mappings().first()
        
        write_to_server_log(f"Role created successfully: {title}")
        return dict(created) if created else {"title": title, "id": None}
        
    except Exception as e:
        db.rollback()
        error_msg = str(e)
        
        if "Duplicate entry" in error_msg or "1062" in error_msg:
            raise Exception(f"Role with title '{title}' already exists")
        
        write_to_server_log(f"Error in create_role_service: {error_msg}")
        raise Exception(f"Failed to create role: {error_msg}")


def get_role_by_id_service(role_id: int, db: Session):
    result = db.execute(
        text("SELECT * FROM roles WHERE id = :id"),
        {"id": role_id},
    ).mappings().first()
    return dict(result) if result else None


def list_roles_service(
    db: Session,
    searchdata: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    pagination: bool = True,
    page: int = 1,
    per_page: Optional[int] = 10,
    is_role_active: Optional = None  
):
    """
    Service function to list roles with filters and pagination
    Excludes Super Admin role (id=1) from the response
    If pagination=False, returns all records without pagination
    is_role_active accepts: true/false, 1/0, 'true'/'false', '1'/'0'
    """
    try:
        base_query = """
            SELECT id, title, is_role_active,
                   DATE_FORMAT(created_at, '%Y-%m-%dT%H:%i:%s') as created_at,
                   DATE_FORMAT(updated_at, '%Y-%m-%dT%H:%i:%s') as updated_at
            FROM roles 
            WHERE id != 1
        """
        
        count_query = """
            SELECT COUNT(*) as total 
            FROM roles 
            WHERE id != 1
        """
        
        params = {}
        
        if is_role_active is not None:
            if isinstance(is_role_active, bool):
                active_value = 1 if is_role_active else 0
            elif isinstance(is_role_active, int):
                active_value = is_role_active
            elif isinstance(is_role_active, str):
                if is_role_active.lower() in ['true', '1']:
                    active_value = 1
                elif is_role_active.lower() in ['false', '0']:
                    active_value = 0
                else:
                    active_value = int(is_role_active)
            else:
                active_value = int(is_role_active)
            
            base_query += " AND is_role_active = :is_role_active"
            count_query += " AND is_role_active = :is_role_active"
            params["is_role_active"] = active_value
        
        if searchdata:
            search_condition = " AND title ILIKE :search"
            base_query += search_condition
            count_query += search_condition
            params["search"] = f"%{searchdata}%"
        
        if from_date:
            base_query += " AND DATE(created_at) >= :from_date"
            count_query += " AND DATE(created_at) >= :from_date"
            params["from_date"] = from_date
            
        if to_date:
            base_query += " AND DATE(created_at) <= :to_date"
            count_query += " AND DATE(created_at) <= :to_date"
            params["to_date"] = to_date
        
        count_result = db.execute(text(count_query), params).first()
        total_count = count_result[0] if count_result else 0
        
        base_query += " ORDER BY id ASC"
        
        if pagination and per_page:
            base_query += " LIMIT :limit OFFSET :offset"
            offset = (page - 1) * per_page
            params["limit"] = per_page
            params["offset"] = offset
        
        result = db.execute(text(base_query), params).mappings().all()
        
        roles_list = []
        for r in result:
            role_dict = dict(r)
            role_dict['is_role_active'] = bool(role_dict['is_role_active'])
            roles_list.append(role_dict)
        
        if pagination and per_page:
            total_pages = (total_count + per_page - 1) // per_page if per_page > 0 else 0
        else:
            total_pages = 1
        
        return {
            "roles": roles_list,
            "total": total_count,
            "total_pages": total_pages
        }
        
    except Exception as e:
        write_to_server_log(f"Error in list_roles_service: {str(e)}")
        import traceback
        write_to_server_log(f"Traceback: {traceback.format_exc()}")
        raise Exception(f"Error in list_roles_service: {str(e)}")


def update_role_service(role_id: int, payload: dict, db: Session):
    existing = get_role_by_id_service(role_id, db)
    if not existing:
        return None

    update_fields = []
    params = {"id": role_id}

    if "title" in payload:
        update_fields.append("title = :title")
        params["title"] = payload.get("title")

    if not update_fields:
        return existing

    update_fields.append("updated_at = NOW()")

    db.execute(
        text(
            f"""
            UPDATE roles
            SET {", ".join(update_fields)}
            WHERE id = :id
            """
        ),
        params,
    )
    db.commit()
    return get_role_by_id_service(role_id, db)


def delete_role_service(role_id: int, db: Session):
    existing = get_role_by_id_service(role_id, db)
    if not existing:
        return None

    db.execute(text("DELETE FROM roles WHERE id = :id"), {"id": role_id})
    db.commit()
    return {"id": role_id, "deleted": True}

def update_role_status_service(role_id: int, is_role_active: int, db: Session):
    """
    Service function to update role active status
    """
    try:
        existing = db.execute(
            text("SELECT id, title, is_role_active FROM roles WHERE id = :id"),
            {"id": role_id}
        ).mappings().first()
        
        if not existing:
            return None
        
        existing_dict = dict(existing)
        
        if role_id == 1 and is_role_active == 0:
            raise Exception("Cannot deactivate Super Admin role")
        
        db.execute(
            text("""
                UPDATE roles 
                SET is_role_active = :is_role_active, 
                    updated_at = NOW()
                WHERE id = :id
            """),
            {
                "id": role_id,
                "is_role_active": is_role_active
            }
        )
        db.commit()
        
        updated_role = db.execute(
            text("""
                SELECT id, title, is_role_active, 
                       DATE_FORMAT(created_at, '%Y-%m-%dT%H:%i:%s') as created_at,
                       DATE_FORMAT(updated_at, '%Y-%m-%dT%H:%i:%s') as updated_at
                FROM roles 
                WHERE id = :id
            """),
            {"id": role_id}
        ).mappings().first()
        
        write_to_server_log(f"Role {role_id} status updated to: {is_role_active}")
        
        return dict(updated_role) if updated_role else None
        
    except Exception as e:
        db.rollback()
        error_msg = str(e)
        write_to_server_log(f"Error in update_role_status_service: {error_msg}")
        import traceback
        write_to_server_log(f"Traceback: {traceback.format_exc()}")
        raise Exception(f"Failed to update role status: {error_msg}")