from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class BuildingUnitCreate(BaseModel):
    building_id: int
    level_id: int
    unit_no: int
    unit_name:str

class BuildingUnitOut(BuildingUnitCreate):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True
