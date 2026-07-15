from sqlalchemy import Column, Integer, String, TIMESTAMP, func
from DB.db import Base

class Camera(Base):
    __tablename__ = "camera_type"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, server_default=func.now(), onupdate=func.now())
