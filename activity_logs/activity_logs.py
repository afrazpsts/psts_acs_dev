from sqlalchemy import Column, BigInteger, String, TIMESTAMP, Text, Boolean
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.sql import func
from DB.db import Base

class ActivityLogs(Base):
    __tablename__ = "activity_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    company_name = Column(String(191), nullable=True)
    action = Column(String(100), nullable=False)       
    module_name = Column(String(100), nullable=False)    
    record_id = Column(String(100), nullable=True)     
    description = Column(String(255), nullable=True)
    old_data = Column(JSON, nullable=True)              
    new_data = Column(JSON, nullable=True)            
    ip_address = Column(String(50), nullable=True)

    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
