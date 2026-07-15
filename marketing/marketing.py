from sqlalchemy import Column, BigInteger, SmallInteger, String, Text, Date, Time, DateTime, TIMESTAMP
from sqlalchemy.sql import func
from DB.db import Base

class Marketing(Base):
    __tablename__ = "marketing"

    id = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False)
    uuid = Column(String(50), nullable=True)
    status_id = Column(BigInteger, nullable=True)
    marketing_type_id = Column(BigInteger, nullable=True)
    property_id = Column(BigInteger, nullable=True)
    common_area_id = Column(BigInteger, nullable=True)
    address = Column(Text, nullable=True)
    phone = Column(String(20), nullable=True)
    country_code = Column(String(8), nullable=True)
    email = Column(String(191), nullable=True)
    title = Column(String(50), nullable=False)
    subtext = Column(String(191), nullable=True)
    description = Column(Text, nullable=True)
    duration_start_date = Column(Date, nullable=True)
    duration_end_date = Column(Date, nullable=True)
    duration_from_time = Column(Time, nullable=True)
    duration_end_time = Column(Time, nullable=True)
    location_name = Column(String(191), nullable=True)
    map_link = Column(String(191), nullable=True)
    website = Column(String(191), nullable=True)
    terms_condition = Column(Text, nullable=True)
    cover_image = Column(String(191), nullable=True)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    created_by = Column(String(191), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=True)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=True)
    announcement_type = Column(SmallInteger, nullable=True, comment="1 is general, 2 is building alert") 
    is_announcement_active = Column(SmallInteger, nullable=False, server_default='1', comment="0 is inactive, 1 is active")
