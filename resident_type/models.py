from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ResidentTypeCreate(BaseModel):
    name: str
    key: str
    description: Optional[str] = None
    is_employee:Optional[str] = None
    description:Optional[str] = None
    

class ResidentTypeOut(ResidentTypeCreate):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


