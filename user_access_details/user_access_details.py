from sqlalchemy import Column, BigInteger, Integer, Date, DateTime, ForeignKey, TIMESTAMP
from sqlalchemy.sql import func
from DB.db import Base

class UserAccessDetail(Base):
    __tablename__ = "user_access_details"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user_personal_details.id"), nullable=False) 
    residency_type_id = Column(BigInteger, ForeignKey("residency_type.id"), nullable=False)
    building_id = Column(BigInteger, ForeignKey("property_building.id"), nullable=False)
    level_id = Column(BigInteger, ForeignKey("building_level.id"), nullable=False)
    unit_id = Column(BigInteger, ForeignKey("building_units.id"), nullable=False)

    join_date = Column(Date, nullable=False)
    access_start = Column(DateTime, nullable=False)
    access_end = Column(DateTime, nullable=False)

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=func.now())
