from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class BuildingLevelCreate(BaseModel):
    building_id: int
    area_type_id: int
    level: str
    total_unit: int = 0
    running_number: int = 0
    is_assign = Optional[int] = None
    start: Optional[int] = None
    end: Optional[int] = None

class BuildingLevelOut(BuildingLevelCreate):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True
