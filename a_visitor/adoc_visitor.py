from sqlalchemy import Column, Integer, String, Date,TIMESTAMP,func,Boolean,JSON
from DB.db import Base 

class AdocVisitor(Base):
    __tablename__ = "adoc_visitor"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=False, nullable=True)
    building_id = Column(String(200), nullable=True)
    level_id = Column(String(200), nullable=False)
    unit_id = Column(String(200), nullable=False)
    phone = Column(String(200),nullable=True)
    purpose_visit = Column(String(255), nullable=True)
    card_no = Column(String(250),nullable=True,unique=True)
    valid = Column(JSON, nullable=True) 
    qr_token = Column(String(50), nullable=False)
    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, server_default=func.now(), onupdate=func.now())
