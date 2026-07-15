from pydantic import BaseModel
from typing import Optional



class PropertyCommonAreaCreate(BaseModel):
    common_area_name: str
    description: Optional[str] = None
    is_part_of_building: bool
    property_id: Optional[int] = None
    building_id: Optional[int] = None
    level_id: Optional[int] = None