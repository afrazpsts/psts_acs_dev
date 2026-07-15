from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime


class VehicleTypeAmount(BaseModel):
    """Model for vehicle type and amount pair"""
    vehicle_type_id: str = Field(..., description="Vehicle type identifier (e.g., car, motorcycle, truck)")
    amount: str = Field(..., description="Amount for this vehicle type")
    billing_period: Optional[str] = Field(None, description="Billing period (e.g., monthly, yearly, quarterly)")
    
    @validator('amount')
    def validate_amount(cls, v):
        if not v:
            raise ValueError('Amount cannot be empty')
        amount_str = v.replace('$', '').replace(',', '')
        try:
            float(amount_str)
        except ValueError:
            raise ValueError(f'Invalid amount format: {v}')
        return v
    
    @validator('billing_period')
    def validate_billing_period(cls, v):
        if v == "":
            return None
        return v


class VehicleConfigurationCreate(BaseModel):
    """Model for creating vehicle configuration"""
    no_of_vehicle_free_slot: str = Field(default="0", description="Number of free vehicle slots")
    vehicle_configurations: List[VehicleTypeAmount] = Field(..., description="List of vehicle types and their amounts")
    
    @validator('no_of_vehicle_free_slot')
    def validate_free_slot(cls, v):
        try:
            int(v)
        except ValueError:
            raise ValueError(f'Invalid number format: {v}')
        return v


class VehicleConfigurationUpdate(BaseModel):
    """Model for updating vehicle configuration"""
    no_of_vehicle_free_slot: Optional[str] = Field(None, description="Number of free vehicle slots")
    vehicle_configurations: Optional[List[VehicleTypeAmount]] = Field(None, description="List of vehicle types and their amounts")


class VehicleConfigurationResponse(BaseModel):
    """Model for vehicle configuration response"""
    id: int
    no_of_vehicle_free_slot: str
    vehicle_type_id: str
    amount: str
    billing_period: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class VehicleConfigurationListResponse(BaseModel):
    """Model for list response"""
    configurations: List[VehicleConfigurationResponse]
    total: int
    total_pages: int