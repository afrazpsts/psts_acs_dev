

from sqlalchemy import Column, BigInteger, String, Integer, ForeignKey, TIMESTAMP, func
from DB.db import Base  

class BlockBuilding(Base):
    __tablename__ = "block_building"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    building_id = Column(BigInteger, ForeignKey("property_building.id"), nullable=False)
    block_id = Column(BigInteger, ForeignKey("block_building.id"), nullable=False)
    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, server_default=func.now(), onupdate=func.now())
