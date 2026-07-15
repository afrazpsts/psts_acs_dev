from pydantic import BaseModel
from datetime import date, datetime

class UserAccessDetailBase(BaseModel):
    residency_type_id: int
    building_id: int
    user_id:int
    level_id: int
    unit_id: int
    join_date: date
    access_start: datetime
    access_end: datetime

class UserAccessDetailCreate(UserAccessDetailBase):
    pass

class UserAccessDetailOut(UserAccessDetailBase):
    id: int
    class Config:
        orm_mode = True
