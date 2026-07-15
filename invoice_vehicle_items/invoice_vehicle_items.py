from sqlalchemy import Column, Integer, String, TIMESTAMP, func, Float, ForeignKey, Text
from DB.db import Base

class InvoiceVehicleItems(Base):
    __tablename__ = "invoice_vehicle_items"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey('invoice_master.id', ondelete='CASCADE'), nullable=False)
    
    vehicle_id = Column(Integer, nullable=False, comment="Vehicle ID from vehicle master")
    iu_number = Column(String(50), nullable=True, comment="IU number")
    vehicle_number = Column(String(50), nullable=False, comment="Vehicle registration number")
    vehicle_type_id = Column(Integer, ForeignKey('vehicle_type.id'), nullable=False)
    
    sub_total = Column(Float, default=0.00, nullable=False)
    extra_amount = Column(Float, default=0.00, nullable=False)
    gst = Column(Float, default=0.00, nullable=False)
    total_amount = Column(Float, default=0.00, nullable=False)
    discount = Column(Float, default=0.00, nullable=True)
    
    description = Column(Text, nullable=True)
    created_by = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, server_default=func.now(), onupdate=func.now())