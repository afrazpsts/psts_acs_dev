from sqlalchemy import Column, Integer, String, DateTime, func
from DB.db import Base  

class UserEmployee(Base):
    __tablename__ = "device_employee_number"   

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    emp_no = Column(String(50), unique=True, nullable=False)  
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now(), server_default=func.now())
