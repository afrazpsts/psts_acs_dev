from sqlalchemy import Column, BigInteger, String, TIMESTAMP,Boolean
from sqlalchemy.sql import func
from DB.db import Base


class VehicleConfiguration(Base):
    __tablename__ = "vehicle_configurations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    no_of_vehicle_free_slot = Column(String(100), nullable=True, server_default="0")
    vehicle_type_id = Column(String(100), nullable=True,unique=True)
    Amount = Column(String(200), nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now()
    )

