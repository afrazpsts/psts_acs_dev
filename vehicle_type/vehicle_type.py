from sqlalchemy import Column, Integer, String, Date,TIMESTAMP,func,Boolean
from DB.db import Base 

class VehicleType(Base):
    __tablename__ = "vehicle_type"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), nullable=False)
    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, server_default=func.now(), onupdate=func.now())
    is_enable = Column(Boolean, default=True, nullable=False, comment="Enable/disable vehicle type")
