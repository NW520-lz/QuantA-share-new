from typing import Any

from pydantic import BaseModel, Field


class MarketDailyQuery(BaseModel):
    symbol: str
    start_date: str
    end_date: str


class MarketDataPoint(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float = 0.0


class MarketDailyResponse(BaseModel):
    symbol: str
    data: list[MarketDataPoint]


class MarketOverviewResponse(BaseModel):
    data: list[dict[str, Any]]


class CandidateItem(BaseModel):
    symbol: str
    name: str
    price: float
    stop_loss: float
    r_value: float
    volume_ratio: float
    status: str = Field(pattern="^(green|yellow|red)$")
    should_buy: bool = False
    signal_type: str | None = None


class WatchlistItem(BaseModel):
    title: str
    change_pct: float
    bars: list[int]


class MarketCandidatesResponse(BaseModel):
    progress_pct: int = Field(ge=0, le=100)
    sentiment_label: str
    sentiment_score: float
    candidates: list[CandidateItem]
    watchlist: list[WatchlistItem]
