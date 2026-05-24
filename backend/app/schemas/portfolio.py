from typing import Optional

from pydantic import BaseModel, Field


class RiskRequest(BaseModel):
    account_equity: float = Field(gt=0)
    price: float = Field(gt=0)
    max_risk_pct: float = Field(default=0.02, gt=0, lt=1)
    stop_loss_pct: float = Field(default=0.05, gt=0, lt=1)
    take_profit_pct: float = Field(default=0.3, gt=0, lt=5)
    max_position_pct: float = Field(default=0.7, gt=0, lt=1)
    beta: Optional[float] = None


class RiskResponse(BaseModel):
    max_shares: float
    max_position_value: float
    stop_loss_price: Optional[float]
    take_profit_price: Optional[float]
    risk_pct_used: float
    beta: Optional[float] = None


class DashboardCandidate(BaseModel):
    symbol: str
    name: str
    price: float
    stop_loss: float
    take_profit: float
    risk_pct: float
    tag: str


class AllocationItem(BaseModel):
    name: str
    value_pct: float


class PortfolioDashboard(BaseModel):
    updated_at: str
    candidates: list[DashboardCandidate]
    positions: list[dict]
    total_position_pct: float
    allocation: list[AllocationItem]
    max_single_position_pct: float
    beta: float
    max_drawdown_pct: float
    risk_hint: str
