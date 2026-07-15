from sqlalchemy import Column, BigInteger, Integer, String, TIMESTAMP, ForeignKey
from sqlalchemy.sql import func
from DB.db import Base

class UserEmergencyContact(Base):
    __tablename__ = "user_emergency"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user_personal_details.id"), nullable=False)  
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    email = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    country_code = Column(String(10), nullable=True)
    nationality = Column(String(100), nullable=True)
    gender = Column(String(10), nullable=True)
    relationship = Column(String(50), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=func.now())
