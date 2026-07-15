from sqlalchemy import Column, Integer, String, TIMESTAMP, func, Boolean, Date, Enum as SQLEnum
from DB.db import Base
import enum

class PeriodType(str, enum.Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"

class MonthOptionType(str, enum.Enum):
    DATE = "date"
    DAY = "day"

class EndType(str, enum.Enum):
    NEVER = "never"
    ON = "on"
    AFTER = "after"

class RecurringInvoiceSettings(Base):
    __tablename__ = "recurring_invoice_settings"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, nullable=False, comment="Reference to invoice_master.id")
    
    repeat_every = Column(Integer, nullable=False, default=1)
    period = Column(SQLEnum(PeriodType), nullable=False, default=PeriodType.MONTH)
    
    month_option = Column(SQLEnum(MonthOptionType), nullable=True, comment="date or day")
    day_of_month = Column(Integer, nullable=True, comment="For month_option='date' (1-31)")
    weekday = Column(Integer, nullable=True, comment="For month_option='day' (0=Monday to 6=Sunday)")
    week_number = Column(Integer, nullable=True, comment="For month_option='day' (1=first, 2=second, 3=third, 4=fourth, -1=last)")
    selected_days = Column(String(255), nullable=True, comment="JSON array of selected days for week recurrence")
    
    year_month = Column(Integer, nullable=True, comment="Month for yearly recurrence (1-12)")
    year_day = Column(Integer, nullable=True, comment="Day for yearly recurrence (1-31)")
    
    end_type = Column(SQLEnum(EndType), nullable=False, default=EndType.NEVER)
    end_date = Column(Date, nullable=True, comment="End date when end_type='on'")
    after_occurrences = Column(Integer, nullable=True, comment="Number of occurrences when end_type='after'")
    
    next_invoice_date = Column(Date, nullable=True, comment="Next scheduled invoice date")
    last_generated_date = Column(Date, nullable=True, comment="Last time invoice was generated")
    total_generated = Column(Integer, default=0, comment="Total number of invoices generated so far")
    is_active = Column(Boolean, default=True, comment="Whether recurring schedule is active")
    
    created_at = Column(TIMESTAMP, nullable=True, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, server_default=func.now(), onupdate=func.now())