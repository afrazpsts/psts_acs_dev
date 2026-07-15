from sqlalchemy import Column, BigInteger, String, TIMESTAMP,Integer
from sqlalchemy.sql import func
from DB.db import Base

class Device(Base):
    __tablename__ = "camera_devices"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    ip = Column(String(45), nullable=False, unique=True)
    building_id = Column(Integer, nullable=True)
    common_building = Column(Integer, nullable=True)
    type = Column(String(50), nullable=False)
    port = Column(String(10), nullable=False)
    user_name = Column(String(100), nullable=True)
    password = Column(String(100), nullable=True)

    deleted_at = Column(TIMESTAMP, nullable=True)
    created_date = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_date = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
