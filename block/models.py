from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class BlockCreate(BaseModel):
    name: str
    level_ids: Optional[List[int]] = None 
    building_ids: Optional[List[int]] = None  
    description: Optional[str] = None
    block_type: Optional[str] = None

class BlockOut(BlockCreate):
    id: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True
