from sqlalchemy import Column, BigInteger, String, TIMESTAMP, Boolean, Enum, Integer, DateTime
from sqlalchemy.sql import func
from DB.db import Base

class Users(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), nullable=True, unique=True)
    phone = Column(String(20), nullable=True) 
    password = Column(String(255), nullable=True)
    company_id = Column(String(100), nullable=True)
    role_id = Column(String(55), nullable=True)
    is_verified = Column(Boolean, nullable=False, default=False)  
    otp = Column(String(100), nullable=True)
    otp_expiry = Column(String(100), nullable=True)
    created_by = Column(String(55), nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
    sub_user_role = Column(String(100), nullable=True)

    is_user_active = Column(
        Enum('true', 'false', name='is_user_active_enum'),
        nullable=False,
        server_default='true'
    )

    on_board_date = Column(String(255), nullable=True)
    off_board_date = Column(String(255), nullable=True)