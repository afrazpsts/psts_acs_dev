from sqlalchemy import Column, Integer, String, TIMESTAMP, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship
from DB.db import Base 

class ResidentFamilyMembers(Base):
    __tablename__ = "resident_family_members"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    main_user_id = Column(Integer, ForeignKey("user_personal_details.id", ondelete="CASCADE"), nullable=False)
    sub_user_id = Column(Integer, ForeignKey("user_personal_details.id", ondelete="CASCADE"), nullable=False)
    # relationship = Column(String(50), nullable=True)
    is_primary = Column(Boolean, nullable=False, default=False)
    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, server_default=func.now(), onupdate=func.now())
    
    main_user = relationship("UserPersonalDetails", foreign_keys=[main_user_id], backref="family_members")
    sub_user = relationship("UserPersonalDetails", foreign_keys=[sub_user_id], backref="main_family")