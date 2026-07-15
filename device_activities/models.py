from pydantic import BaseModel
from datetime import datetime

class DeviceActivityOut(BaseModel):
    id: int
    device_activities: dict
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
class EventQuery(BaseModel):
    device_id: int
    startTime: str
    endTime: str
    maxResults: int = 50