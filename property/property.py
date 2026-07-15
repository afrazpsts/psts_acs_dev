from sqlalchemy import Column, BigInteger, Integer, String, Text, TIMESTAMP, SmallInteger
from sqlalchemy.sql import func
from DB.db import Base

class Property(Base):
    __tablename__ = "property"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(String(50), nullable=False)
    slug = Column(String(30), nullable=False)
    type = Column(SmallInteger, nullable=False, default=1)
    project_developer = Column(String(191), nullable=True)
    completion_year = Column(Integer, nullable=True)
    tenure_year = Column(Integer, nullable=True)
    total_units = Column(Integer, nullable=True)
    name = Column(String(50), nullable=False)
    email = Column(String(191), nullable=True)
    phone = Column(String(20), nullable=False)
    country_code = Column(String(8), nullable=False)
    address = Column(Text, nullable=True)
    country = Column(String(20), nullable=False)
    city = Column(String(20), nullable=False)
    zipcode = Column(String(6), nullable=True)
    description = Column(Text, nullable=True)
    property_logo = Column(String(191), nullable=True)
    cover_image = Column(String(191), nullable=True)
    status = Column(BigInteger, nullable=False, default=4)
    completed_step = Column(SmallInteger, nullable=False, default=0)
    company_id = Column(BigInteger, nullable=True)
    created_by = Column(BigInteger, nullable=True)
    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, server_default=func.now(), onupdate=func.now())
    deleted_at = Column(TIMESTAMP, nullable=True)
