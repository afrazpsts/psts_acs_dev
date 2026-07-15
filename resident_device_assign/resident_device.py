from sqlalchemy import Column, Integer, String, Boolean, DateTime, BigInteger, JSON,ForeignKey
from sqlalchemy.sql import func
from DB.db import Base

class ResidentDeviceAssign(Base):
    __tablename__ = "resident_device_assign"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user_personal_details.id"), nullable=False)
    device_id = Column(BigInteger, nullable=False)
    device_ip = Column(String(50), nullable=True)
    employee_no = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)
    gender = Column(String(10), nullable=True)
    valid = Column(JSON, nullable=True)  
    door_right = Column(String(20), nullable=True)
    right_plan = Column(JSON, nullable=True)  
    local_ui_right = Column(Boolean, nullable=True, default=True)
    max_open_door_time = Column(Integer, nullable=True, default=0)
    user_verify_mode = Column(String(50), nullable=True)
    floor_numbers = Column(JSON, nullable=True)  
    call_numbers = Column(JSON, nullable=True)   
    password = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
