from sqlalchemy import Column, BigInteger, String, Text, TIMESTAMP
from sqlalchemy.sql import func
from DB.db import Base

class Company(Base):
    __tablename__ = "company"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    email = Column(String(191), nullable=True)
    phone = Column(String(20), nullable=True)
    country_code = Column(String(8), nullable=True)
    country = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    deleted_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, server_default=func.now(), onupdate=func.now())
