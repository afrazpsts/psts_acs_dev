from sqlalchemy import Column, Integer, BigInteger, ForeignKey, DateTime, func
from DB.db import Base 

class AssignCamera(Base):
    __tablename__ = "assign_devices"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(BigInteger, ForeignKey("camera_devices.id"))
    building_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
