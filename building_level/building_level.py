from sqlalchemy import Column, BigInteger, Integer, String, TIMESTAMP, ForeignKey
from sqlalchemy.sql import func
from DB.db import Base
from sqlalchemy import Boolean

class BuildingLevel(Base):
    __tablename__ = "building_level"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    building_id = Column(BigInteger, ForeignKey("property_building.id", ondelete="CASCADE"), nullable=False)
    is_assign = Column(Boolean, nullable=False, default=False)
    area_type_id = Column(BigInteger, ForeignKey("level_area_type.id"))
    level = Column(String(20), nullable=False)
    total_unit = Column(Integer, nullable=False, default=0)
    running_number = Column(Integer, nullable=False, default=0)
    start = Column(Integer, nullable=True)
    end = Column(Integer, nullable=True)
    created_at = Column(TIMESTAMP, nullable=True, default=None)
    updated_at = Column(TIMESTAMP, nullable=True, default=None, onupdate=func.now())
