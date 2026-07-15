from pydantic import BaseModel, EmailStr
from typing import Optional

class UserEmergencyContactBase(BaseModel):
    first_name: str
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    user_id: Optional[int] = None
    phone: Optional[str] = None
    country_code: Optional[str] = None
    nationality: Optional[str] = None
    gender: Optional[str] = None
    relationship: Optional[str] = None

class UserEmergencyContactCreate(UserEmergencyContactBase):
    pass

class UserEmergencyContactOut(UserEmergencyContactBase):
    id: int

    class Config:
        orm_mode = True
