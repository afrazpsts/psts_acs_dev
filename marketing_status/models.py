from pydantic import BaseModel
from typing import Optional

class MarketingStatusCreate(BaseModel):
    key: str
    name: str
    description: Optional[str] = None

class MarketingStatusOut(BaseModel):
    id: int
    key: str
    name: str
    description: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]

    class Config:
        orm_mode = True