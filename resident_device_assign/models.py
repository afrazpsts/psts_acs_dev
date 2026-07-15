from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

class ValidTime(BaseModel):
    enable: bool
    beginTime: datetime
    endTime: datetime
    timeType: str

class ValidTimeUpdate(BaseModel):
    enable: bool
    beginTime: str
    endTime: str
    timeType: str = "local"

class RightPlan(BaseModel):
    planTemplateNo: int
    doorNo: int

class AddPersonRequest(BaseModel):
    name: str
    valid: ValidTime
    gender: Optional[str] = None
    employee_no: Optional[str] = None  
    image_upload_path: Optional[str] = None
    door_right: Optional[str] = "1"
    right_plan: Optional[List[RightPlan]] = []
    local_ui_right: Optional[str] = "true"
    max_open_door_time: Optional[int] = 3
    user_verify_mode: Optional[str] = "cardAndFingerprint"
    floor_numbers: Optional[List[int]] = []
    call_numbers: Optional[List[str]] = []
    password: Optional[str] = ""
    user_id: Optional[int] = 1

class UpdatePersonRequest(BaseModel):
    user_id: int
    employee_no: str
    name: str
    gender: str
    valid: ValidTime       # <-- use this
    door_right: str
    local_ui_right: bool
    max_open_door_time: int
    user_verify_mode: str
    floor_numbers: list
    call_numbers: list
    password: str


# class UpdateValidTime(BaseModel):
#     enable: bool
#     beginTime: str
#     endTime: str
#     timeType: str = "local"