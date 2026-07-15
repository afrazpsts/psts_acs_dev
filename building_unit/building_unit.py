from sqlalchemy import Column, BigInteger, Integer, String, TIMESTAMP, ForeignKey,Boolean
from sqlalchemy.sql import func
from DB.db import Base

class BuildingUnit(Base):
    __tablename__ = "building_units"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    level_id = Column(BigInteger, ForeignKey("building_level.id", ondelete="CASCADE"), nullable=False)
    building_id = Column(BigInteger, ForeignKey("property_building.id", ondelete="CASCADE"), nullable=False)
    unit_no = Column(String(20), nullable=False)
    disabled = Column(Boolean, nullable=False, default=False)
    unit_name = Column(Integer, nullable=False, default=0)
    created_at = Column(TIMESTAMP, nullable=True, default=None)
    updated_at = Column(TIMESTAMP, nullable=True, default=None, onupdate=func.now())
