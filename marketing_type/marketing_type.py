from sqlalchemy import Column, BigInteger, String, Text, TIMESTAMP
from sqlalchemy.sql import func
from DB.db import Base 

class MarketingType(Base):
    __tablename__ = "marketing_type"

    id = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False)
    key = Column(String(20), nullable=False)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=True)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=True)


