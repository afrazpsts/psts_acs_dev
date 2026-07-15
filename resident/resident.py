from sqlalchemy import Column, BigInteger, Integer, String, Text, TIMESTAMP, SmallInteger
from sqlalchemy.sql import func
from DB.db import Base

class Resident(Base):
    __tablename__ = "residency"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    first_name = Column(String(191), nullable=False)
    last_name = Column(String(191), nullable=False)
    dob = Column(String(191), nullable=False)
    nationality = Column(String(191), nullable=False)
    gender = Column(String(191), nullable=False)
    identity_number = Column(String(191), nullable=False)
    phone = Column(String(191), nullable=False)
    country_code = Column(String(191), nullable=False)
    address = Column(String(191), nullable=False)
    country = Column(String(191), nullable=False)
    zipcode = Column(String(191), nullable=False)
    email = Column(String(191), nullable=False)
    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, server_default=func.now(), onupdate=func.now())
