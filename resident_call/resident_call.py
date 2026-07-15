from sqlalchemy import Column, BigInteger, String, Enum, TIMESTAMP, ForeignKey
from sqlalchemy.sql import func
from DB.db import Base
import enum


class CallStatus(enum.Enum):
    ringing = "ringing"
    answered = "answered"
    ended = "ended"
    missed = "missed"


class Call(Base):
    __tablename__ = "resident_call"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    call_id = Column(String(36), unique=True, nullable=False)  
    unit_id = Column(String(100), nullable=False)
    user_id = Column(String(100), nullable=False)
    building_id = Column(String(100), nullable=False)
    level_id = Column(String(100), nullable=False)
    purpose_of_visit = Column(String(255), nullable=True)
    name = Column(String(255), nullable=True)
    delivery_id = Column(String(100), nullable=False)
    status = Column(Enum(CallStatus), nullable=False, default=CallStatus.ringing)
    answered_by = Column(String(100), nullable=True)
    started_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    ended_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, server_default=func.now(), onupdate=func.now())
