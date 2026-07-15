from sqlalchemy import Column, BigInteger, String, TIMESTAMP,Boolean
from sqlalchemy.sql import func
from DB.db import Base


class Roles(Base):
    __tablename__ = "roles"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(String(100), nullable=False, unique=True)
    is_role_active = Column(Boolean, nullable=False, default=True, server_default="1")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now()
    )

