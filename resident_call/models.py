from pydantic import BaseModel

class CallStartPayload(BaseModel):
    unit_id: str
    delivery_id: str
    # kiosk_id: str 
    building_id: str
    level_id: str
    purpose_of_visit: str 
    name: str  

class RejectPayload(BaseModel):
    call_id: str
    rejected_by: str

class OpenDoorPayload(BaseModel):
    call_id: str