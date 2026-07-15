from sqlalchemy.orm import Session
from sqlalchemy.sql import text
from fastapi import HTTPException
from datetime import datetime
from .model import PropertyCreate
import traceback

async def create_property(property: PropertyCreate, db: Session):
    try:
        query = text("""
            INSERT INTO property (
                title, slug, type, project_developer, completion_year, tenure_year,
                total_units, name, email, phone, country_code, address, country,
                city, zipcode, description, property_logo, cover_image, status,
                completed_step, company_id, created_by, created_at, updated_at
            ) VALUES (
                :title, :slug, :type, :project_developer, :completion_year, :tenure_year,
                :total_units, :name, :email, :phone, :country_code, :address, :country,
                :city, :zipcode, :description, :property_logo, :cover_image, :status,
                :completed_step, :company_id, :created_by, :created_at, :updated_at
            )
        """)
        now = datetime.now()
        values = property.dict()
        values.update({"created_at": now, "updated_at": now})
        db.execute(query, values)
        db.commit()

        result = db.execute(text("SELECT * FROM property WHERE slug = :slug"), {"slug": property.slug})
        created_property = result.fetchone()
        return dict(created_property._mapping)

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Insert failed: {str(e)}")


def list_properties(db: Session):
    try:
        result = db.execute(text("SELECT * FROM property ORDER BY id DESC"))
        rows = result.fetchall()
        return [dict(row._mapping) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fetch failed: {str(e)}")


def delete_property(property_id: int, db: Session):
    try:
        result = db.execute(
            text("DELETE FROM property WHERE id = :id"),
            {"id": property_id}
        )

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Property not found.")

        db.commit()

        return {
            "status": 200,
            "message": f"Property with id {property_id} deleted successfully."
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Delete failed.")
