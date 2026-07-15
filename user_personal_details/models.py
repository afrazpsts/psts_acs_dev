from pydantic import BaseModel, EmailStr,constr
from typing import Optional
from datetime import date,datetime

class UserPersonalDetailsBase(BaseModel):
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    email: EmailStr
    password: Optional[str] = None
    dob: Optional[date] = None
    gender: Optional[str] = None
    nationality: Optional[str] = None
    identity_number: Optional[str] = None
    phone: Optional[str] = None
    country_code: Optional[str] = None
    address: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    otp: Optional[str] = None  
    otp_expiry: Optional[datetime] = None 
    zipcode: Optional[str] = None

class UserPersonalDetailsCreate(UserPersonalDetailsBase):
    pass


class EmailVerifyRequest(BaseModel):
    email: EmailStr
    
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    fcm_token: Optional[str] = None

class OTPVerifyRequest(BaseModel):
    email: EmailStr
    otp: str

class ResendOTPRequest(BaseModel):
    email: EmailStr

class LogoutRequest(BaseModel):
    user_id: int
    
class EmailRequest(BaseModel):
    email: EmailStr

class LicensePlateRequest(BaseModel):
    licensePlate: str
    
class UpdatePlateRequest(BaseModel):
    LicensePlate: str
    listType: Optional[str] = ""
    cardNo: Optional[str] = ""
    createTime: Optional[str] = ""
    effectiveTime: Optional[str] = ""

class SetPasswordRequest(BaseModel):
    email: EmailStr
    password: constr(min_length=6)




class UserPersonalDetailsOut(UserPersonalDetailsBase):
    id: int

    class Config:
        orm_mode = True
