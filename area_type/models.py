
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class AreatypeCreate(BaseModel):
    key: str
    type_name: Optional[str] = None
    description: Optional[str] = None

class AreatypegOut(AreatypeCreate):
    id: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True
