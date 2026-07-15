from pydantic import BaseModel
from typing import Optional


class MarketingCreate(BaseModel):
    uuid: Optional[str] = None
    status_id: Optional[int] = 3
    marketing_type_id: Optional[int] = None
    property_id: Optional[int] = None
    common_area_id: Optional[int] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    country_code: Optional[str] = None
    email: Optional[str] = None
    title: str
    subtext: Optional[str] = None
    description: Optional[str] = None
    duration_start_date: Optional[str] = None
    duration_end_date: Optional[str] = None
    duration_from_time: Optional[str] = None
    duration_end_time: Optional[str] = None
    location_name: Optional[str] = None
    map_link: Optional[str] = None
    website: Optional[str] = None
    terms_condition: Optional[str] = None
    cover_image: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    created_by: int