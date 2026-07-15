from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, BigInteger, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from DB.db import Base

class LicensePlateAccess(Base):
    __tablename__ = "license_plate_access" 

    id = Column(Integer, primary_key=True, index=True)
    building_id = Column(Integer, nullable=True)
    resident_id = Column(Integer, nullable=True)
    anpr_device_activities = Column(JSON, nullable=True)
    LicensePlate = Column(String(191), unique=True, nullable=False)
    iu_number = Column(String(100), nullable=True, unique=True)
    listType = Column(String(50), nullable=False)
    vehicleType = Column(String(200), nullable=False)
    createTime = Column(String(255), nullable=True)
    effectiveTime = Column(String(255), nullable=True)
    source = Column(String(20), default="resident", nullable=False, comment="Source of vehicle entry: resident or visitor")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())