from sqlalchemy import Column, BigInteger, JSON, TIMESTAMP,String
from sqlalchemy.sql import func
from DB.db import Base  

class AnprDeviceActivities(Base):
    __tablename__ = "anpr_device_activities"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    anpr_device_activity = Column(JSON, nullable=False)

    resident_id = Column(String(150), nullable=True)
    entry_time = Column(String(200),nullable=True)
    exit_time = Column(String(100),nullable=True)
    
    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, server_default=func.now(), onupdate=func.now())
