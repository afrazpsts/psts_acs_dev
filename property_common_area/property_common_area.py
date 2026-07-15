from sqlalchemy import Column, BigInteger, String, Text, Boolean, ForeignKey, TIMESTAMP
from sqlalchemy.sql import func
from DB.db import Base  

class PropertyCommonArea(Base):
    __tablename__ = "property_common_area"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    common_area_name = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    is_part_of_building = Column(Boolean, nullable=False, default=False)
    
    property_id = Column(BigInteger, ForeignKey("property.id"), nullable=True)
    building_id = Column(BigInteger, ForeignKey("property_building.id"), nullable=True)
    level_id = Column(BigInteger, ForeignKey("building_level.id"), nullable=True)

    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=func.now())
