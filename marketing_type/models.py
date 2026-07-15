
from pydantic import BaseModel
from typing import Optional

class MarketingTypeCreate(BaseModel):
    key: str
    name: str
    description: Optional[str] = None