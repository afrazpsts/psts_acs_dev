from sqlalchemy import Column, BigInteger, Integer, String, Text, TIMESTAMP, JSON
from sqlalchemy.sql import func
from DB.db import Base

class MenuList(Base):
    __tablename__ = "menu_list"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(191), nullable=False)
    key = Column(String(191), nullable=False)
    description = Column(Text, nullable=True)
    navigation = Column(String(191), nullable=True)
    icon_path = Column(String(191), nullable=True)
    active_path = Column(String(191), nullable=True)
    parent_menu_id = Column(Integer, nullable=True)
    allowed_user_role = Column(JSON, nullable=True)
    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, server_default=func.now(), onupdate=func.now())