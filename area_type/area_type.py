

from sqlalchemy import Column, BigInteger, String, Integer, ForeignKey, TIMESTAMP, func
from DB.db import Base  

class AreaType(Base):
    __tablename__ = "level_area_type"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    key = Column(String(55), nullable=False)
    type_name = Column(String(191), nullable=True)
    description = Column(String(191), nullable=True)
    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, server_default=func.now(), onupdate=func.now())
