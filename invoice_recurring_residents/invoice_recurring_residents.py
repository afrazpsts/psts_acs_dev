from sqlalchemy import Column, Integer, TIMESTAMP, func, ForeignKey
from DB.db import Base

class InvoiceRecurringResidents(Base):
    __tablename__ = "invoice_recurring_residents"

    id = Column(Integer, primary_key=True, index=True)
    resident_id = Column(Integer, nullable=False, comment="Resident/User ID")
    invoice_id = Column(Integer, ForeignKey('invoice_master.id', ondelete='CASCADE'), nullable=False)
    building_id = Column(Integer, nullable=False, comment="Building ID")
    level_id = Column(Integer, nullable=True, comment="Building level ID")
    unit_id = Column(Integer, nullable=True, comment="Building unit ID")
    created_by = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, server_default=func.now(), onupdate=func.now())