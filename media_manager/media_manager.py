from sqlalchemy import Column, BigInteger, Integer, String, Float, TIMESTAMP
from sqlalchemy.sql import func
from DB.db import Base


class MediaManager(Base):
    __tablename__ = "media_manager"

    id = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False)

    folder = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    path = Column(String(255), nullable=False)
    module_name = Column(String(255), nullable=False)
    reference_id = Column(Integer, nullable=False)
    file_type = Column(String(150), nullable=False)
    file_size = Column(Float, nullable=False)

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=True)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=True)

