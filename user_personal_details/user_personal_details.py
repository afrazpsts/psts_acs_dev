from sqlalchemy import Column, Integer, String, Date,TIMESTAMP,func,Boolean
from DB.db import Base 

class UserPersonalDetails(Base):
    __tablename__ = "user_personal_details"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(100), nullable=False)
    middle_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    email = Column(String(150), unique=True, nullable=False)
    password = Column(String(210), nullable=True)
    dob = Column(Date, nullable=True)
    gender = Column(String(20), nullable=False)
    nationality = Column(String(100), nullable=True)
    identity_number = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    country_code = Column(String(10), nullable=True)
    address = Column(String(255), nullable=True)
    fcm_token = Column(String(255), nullable=True)
    country = Column(String(100), nullable=True)
    otp = Column(String(100), nullable=True)
    otp_expiry = Column(String(100), nullable=True)
    is_verified = Column(Boolean, nullable=False, default=False)  
    card_no = Column(String(250),nullable=True,unique=True)
    city = Column(String(100), nullable=True)
    zipcode = Column(String(20), nullable=True)
    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, server_default=func.now(), onupdate=func.now())
