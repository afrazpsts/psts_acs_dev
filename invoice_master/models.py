from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import List, Optional
from enum import Enum

class InvoiceStatusEnum(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"

class PaymentStatusEnum(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    PARTIAL = "partial"
    FAILED = "failed"

class PeriodTypeEnum(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"

class MonthOptionTypeEnum(str, Enum):
    DATE = "date"
    DAY = "day"

class EndTypeEnum(str, Enum):
    NEVER = "never"
    ON = "on"
    AFTER = "after"

class VehicleItemCreate(BaseModel):
    vehicle_id: int
    iu_number: Optional[str] = None
    vehicle_number: str
    vehicle_type: int 
    sub_total: str = "0.00"
    extra_amount: float = 0
    gst: str = "0.00"
    total_amount: str = "0.00"
    discount: Optional[str] = ""
    created_by: int

class VehicleItemResponse(BaseModel):
    id: int
    invoice_id: int
    vehicle_id: int
    iu_number: Optional[str]
    vehicle_number: str
    vehicle_type_id: int
    sub_total: float
    extra_amount: float
    gst: float
    total_amount: float
    discount: Optional[float]
    description: Optional[str]
    created_by: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class RecurringSettingsCreate(BaseModel):
    repeatEvery: int = 1
    period: PeriodTypeEnum = PeriodTypeEnum.MONTH
    monthOption: Optional[MonthOptionTypeEnum] = MonthOptionTypeEnum.DATE
    dayOfMonth: Optional[int] = 1
    weekday: Optional[int] = 1
    weekNumber: Optional[int] = 2
    selectedDays: Optional[List[int]] = [1]
    endType: EndTypeEnum = EndTypeEnum.NEVER
    endDate: Optional[str] = ""
    afterOccurrences: Optional[str] = ""
    yearMonth: Optional[int] = 1
    yearDay: Optional[int] = 1

class RecurringSettingsResponse(BaseModel):
    id: int
    invoice_id: int
    repeat_every: int
    period: PeriodTypeEnum
    month_option: Optional[MonthOptionTypeEnum]
    day_of_month: Optional[int]
    weekday: Optional[int]
    week_number: Optional[int]
    selected_days: Optional[str]
    end_type: EndTypeEnum
    end_date: Optional[date]
    after_occurrences: Optional[int]
    year_month: Optional[int]
    year_day: Optional[int]
    next_invoice_date: Optional[date]
    is_active: bool
    
    class Config:
        from_attributes = True

class InvoiceCreate(BaseModel):
    resident_id: str
    building_id: str
    level_id: str
    unit_id: str
    invoice_date: date
    due_date: date
    terms_and_conditions: str = "<p></p>"
    mark_as_recurring: bool = False
    vehicle_items: List[VehicleItemCreate]
    repeatEvery: int = 1
    period: PeriodTypeEnum = PeriodTypeEnum.MONTH
    monthOption: Optional[MonthOptionTypeEnum] = MonthOptionTypeEnum.DATE
    dayOfMonth: Optional[int] = 1
    weekday: Optional[int] = 1
    weekNumber: Optional[int] = 2
    selectedDays: Optional[List[int]] = [1]
    endType: EndTypeEnum = EndTypeEnum.NEVER
    endDate: Optional[str] = ""
    afterOccurrences: Optional[str] = ""
    yearMonth: Optional[int] = 1
    yearDay: Optional[int] = 1

class InvoiceResponse(BaseModel):
    id: int
    invoice_number: str
    resident_id: int
    building_id: int
    level_id: Optional[int]
    unit_id: Optional[int]
    invoice_date: date
    due_date: date
    sub_total: float
    extra_amount: float
    gst: float
    total_amount: float
    discount: Optional[float]
    terms_and_conditions: Optional[str]
    status: InvoiceStatusEnum
    payment_status: PaymentStatusEnum
    mark_as_recurring: bool
    parent_invoice_id: Optional[int]
    created_by: int
    created_at: datetime
    
    class Config:
        from_attributes = True