from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class CompanyCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    country_code: Optional[str] = None
    country: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None

class CompanyOut(CompanyCreate):
    id: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True
