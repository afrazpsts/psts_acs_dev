from sqlalchemy import Column, BigInteger, JSON, TIMESTAMP
from sqlalchemy.sql import func
from DB.db import Base  

class DeviceActivities(Base):
    __tablename__ = "device_activities"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    device_activities = Column(JSON, nullable=False)

    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, server_default=func.now(), onupdate=func.now())
