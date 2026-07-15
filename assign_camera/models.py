from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class AssignCameraCreate(BaseModel):
    device_id: Optional[int]
    building_id: Optional[int]

class AssignCameraOut(BaseModel):
    id: int
    device_id: Optional[int]
    building_id: Optional[int]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    device_name: Optional[str]
    block_name: Optional[str]
