from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class VehicleTypeCreate(BaseModel):
    title: str

class VehicleTypeUpdate(BaseModel):
    title: Optional[str] = None

class VehicleTypeResponse(BaseModel):
    id: int
    title: str
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class VehicleStatusUpdate(BaseModel):
    is_enable: bool