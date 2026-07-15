from sqlalchemy.dialects.mysql import JSON
from sqlalchemy import Column, BigInteger, String, TIMESTAMP, func
from DB.db import Base

class Block(Base):
    __tablename__ = "block"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    Name = Column(String(55), nullable=False)
    block_type = Column(String(55), nullable=False)
    building_ids = Column(JSON,nullable=True)
    level_ids = Column(JSON, nullable=True) 
    description = Column(String(191), nullable=True)
    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, server_default=func.now(), onupdate=func.now())
