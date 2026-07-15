from sqlalchemy import Column, Integer, String, Date,TIMESTAMP,func,Boolean,JSON
from DB.db import Base 

class VisitorQrAssign(Base):
    __tablename__ = "invite_visitor"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    user_id = Column(String(100),nullable=True)
    visitor_id = Column(String(100), nullable=True,unique=True)
    # visit_times = Column(Integer, default=0, nullable=False)
    purpose_visit = Column(String(255), nullable=True)
    card_no = Column(String(250),nullable=True,unique=True)
    phone = Column(String(100),nullable=True)
    valid = Column(JSON, nullable=True)
    qr_token = Column(String(50), nullable=False) 
    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, server_default=func.now(), onupdate=func.now())
