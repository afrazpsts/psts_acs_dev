from pydantic import BaseModel
from datetime import datetime


class CameraBase(BaseModel):
    title: str


class MessageResponse(BaseModel):
    message: str
    
class CameraCreate(CameraBase):
    pass


class CameraUpdate(CameraBase):
    pass


class CameraOut(CameraBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
