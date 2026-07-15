from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class PropertyCreate(BaseModel):
    title: str
    slug: str
    type: Optional[int] = 1
    project_developer: Optional[str] = None
    completion_year: Optional[int] = None
    tenure_year: Optional[int] = None
    total_units: Optional[int] = None
    name: str
    email: Optional[str] = None
    phone: str
    country_code: str
    address: Optional[str] = None
    country: str
    city: str
    zipcode: Optional[str] = None
    description: Optional[str] = None
    property_logo: Optional[str] = None
    cover_image: Optional[str] = None
    status: Optional[int] = 4
    completed_step: Optional[int] = 0
    company_id: Optional[int] = None
    created_by: Optional[int] = None

class PropertyOut(PropertyCreate):
    id: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True
