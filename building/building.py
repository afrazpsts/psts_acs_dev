

from sqlalchemy import Column, BigInteger, String, Integer, ForeignKey, TIMESTAMP, func
from DB.db import Base  
from sqlalchemy import Boolean

class PropertyBuilding(Base):
    __tablename__ = "property_building"
    

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    property_id = Column(BigInteger, nullable=False)
    building_name = Column(String(55), nullable=False,unique=True)
    is_assign = Column(Boolean, nullable=False, default=False)
    import_file_path = Column(String(191), nullable=True)
    address_number = Column(String(191), nullable=True)
    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, server_default=func.now(), onupdate=func.now())
