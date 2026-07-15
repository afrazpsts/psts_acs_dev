from sqlalchemy import Column, Integer, Boolean, TIMESTAMP
from sqlalchemy.sql import func
from DB.db import Base


class UserMenuPermission(Base):
    __tablename__ = "role_menu_permission"
    
    id = Column(Integer, primary_key=True, auto_increment=True)  
    role_id = Column(Integer, nullable=False)
    menu_id = Column(Integer, nullable=False) 
    enabled = Column(Boolean, nullable=True, default=True) 
    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(
        TIMESTAMP,
        nullable=True,
        server_default=func.now(),
        onupdate=func.now()
    )