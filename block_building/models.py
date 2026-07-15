from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class BlockBuildingCreate(BaseModel):
    building_id: int
    block_id: int

class BlockBuildingOut(BlockBuildingCreate):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True
