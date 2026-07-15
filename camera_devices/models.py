from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class DeviceOut(BaseModel):
    id: int
    name: str
    ip: str
    type:str
    port:str
    common_building :Optional[str] = None
    user_name:Optional[str] = None
    password: Optional[str] = None
    created_date: datetime
    updated_date: datetime

    

    class Config:
        orm_mode = True
