from sqlalchemy import Column, Integer, String, TIMESTAMP, func, Float, ForeignKey, Enum as SQLEnum, Text, JSON, DECIMAL
from DB.db import Base
import enum

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class InvoicePayments(Base):
    __tablename__ = "invoice_payments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    invoice_id = Column(Integer, ForeignKey('invoice_master.id', ondelete='CASCADE'), nullable=False, index=True)
    payment_request_id = Column(String(100), nullable=False, index=True)
    reference_number = Column(String(100), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False) 
    payment_url = Column(Text, nullable=True)
    status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.PENDING, nullable=True, index=True)
    hitpay_response = Column(JSON, nullable=True)
    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, server_default=func.now(), onupdate=func.now())