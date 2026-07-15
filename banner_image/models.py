from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class BannerImageBase(BaseModel):
    title: str
    image: str


class BannerImageCreate(BannerImageBase):
    pass


class BannerImageUpdate(BaseModel):
    title: Optional[str] = None
    image: Optional[str] = None


class BannerImageResponse(BannerImageBase):
    id: int
    title: str
    image: str
    logo_image: Optional[str] = None
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True
