from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID | str
    user_id: UUID | str
    symbol: str
    name: Optional[str]
    quantity: float
    avg_price: Optional[float]
    last_price: Optional[float]
    pnl: Optional[float]
    pnl_pct: Optional[float]
    risk_level: Optional[str]
    created_at: datetime
    updated_at: datetime


class PositionUpsert(BaseModel):
    symbol: str
    name: Optional[str] = None
    quantity: float
    avg_price: float
    last_price: Optional[float] = None
    risk_level: Optional[str] = None
