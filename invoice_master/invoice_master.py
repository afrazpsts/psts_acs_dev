from sqlalchemy import Column, Integer, String, Date, TIMESTAMP, func, Boolean, Float, Text, Enum
from DB.db import Base
import enum

class InvoiceStatus(str, enum.Enum):
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    PARTIAL = "partial"
    FAILED = "failed"

class InvoiceMaster(Base):
    __tablename__ = "invoice_master"

    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String(50), unique=True, nullable=False, comment="Unique invoice number")
    resident_id = Column(Integer, nullable=False, comment="Resident/User ID")
    building_id = Column(Integer, nullable=False, comment="Property building ID")
    level_id = Column(Integer, nullable=True, comment="Building level ID")
    unit_id = Column(Integer, nullable=True, comment="Building unit ID")
    
    invoice_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    
    sub_total = Column(Float, default=0.00, nullable=False)
    extra_amount = Column(Float, default=0.00, nullable=False, comment="Handling charges or extra fees")
    gst = Column(Float, default=0.00, nullable=False)
    total_amount = Column(Float, default=0.00, nullable=False)
    discount = Column(Float, default=0.00, nullable=True)
    
    terms_and_conditions = Column(Text, nullable=True)
    status = Column(Enum(InvoiceStatus), default=InvoiceStatus.DRAFT, nullable=False)
    payment_status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    
    mark_as_recurring = Column(Boolean, default=False)
    parent_invoice_id = Column(Integer, nullable=True, comment="Reference to parent invoice for recurring invoices")
    
    created_by = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, server_default=func.now(), onupdate=func.now())