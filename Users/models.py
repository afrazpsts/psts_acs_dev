from pydantic import BaseModel

class AuthUser(BaseModel):
    email: str
    password: str

class OTPVerifyRequest(BaseModel):
    email: str
    otp: str

class SetPasswordRequest(BaseModel):
    email: str
    password: str