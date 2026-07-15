from typing import Optional,Dict, Any
from pydantic import BaseModel
from datetime import datetime

class ValidityPeriod(BaseModel):
    beginTime: datetime
    endTime: datetime


class VisitorQrResponse(BaseModel):
    visitor_id: str
    visitor_name: str
    card_no: str
    visiting_time: str
    valid: Dict[str, Any]
    created_at: datetime



class DeviceRequest(BaseModel):
    user_id: str
    visitor_name: str
    purpose_of_visitor: Optional[str] = None
    phone: Optional[str] = None
    building_id: Optional[int] = None
    vehicle_type: Optional[int] = None
    license_plate: Optional[str] = None 
    iu_number: Optional[str] = None  
    valid_from: str
    valid_to: str
    gender: Optional[str] = None
    
