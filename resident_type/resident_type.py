from sqlalchemy import Column, BigInteger, Integer, String, Text, TIMESTAMP, SmallInteger
from sqlalchemy.sql import func
from DB.db import Base

class ResidentList(Base):
    __tablename__ = "residency_type"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    key = Column(String(191), nullable=False)
    name = Column(String(191), nullable=False)
    is_employee = Column(String(191), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, server_default=func.now(), onupdate=func.now())
