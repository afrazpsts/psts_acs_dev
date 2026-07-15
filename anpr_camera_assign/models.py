from pydantic import BaseModel
from typing import Optional

class AddPlateRequest(BaseModel):
    building_id: Optional[int] = None
    resident_id: Optional[int] = None
    LicensePlate: str
    # vehicle_type: str
    cardNo: Optional[str] = None
    listType: Optional[str] = "allowList"
    createTime: Optional[str] = None
    effectiveTime: Optional[str] = None

class LicensePlateRequest(BaseModel):
    licensePlate: str

class UpdatePlatePayload(BaseModel):
    new_license_plate: str
    cardNo: Optional[str] = None
    listType: Optional[str] = None

class LicensePlateDeletionRequest(BaseModel):
    deleteAllEnabled: bool
    
    

    