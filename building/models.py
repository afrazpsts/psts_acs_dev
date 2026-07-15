
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class PropertyBuildingCreate(BaseModel):
    property_id: int
    building_name: str
    import_file_path: Optional[str] = None
    is_assign: Optional[int] = None
    address_number: Optional[str] = None

class PropertyBuildingOut(PropertyBuildingCreate):
    id: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True
