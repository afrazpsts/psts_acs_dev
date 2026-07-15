from sqlalchemy import Column, Integer, String, DateTime, func
from DB.db import Base  

class BannerImage(Base):
    __tablename__ = "banner_image"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    image = Column(String(500), nullable=False) 
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
