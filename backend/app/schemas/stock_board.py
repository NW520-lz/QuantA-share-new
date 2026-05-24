from typing import Any, Optional

from pydantic import BaseModel, Field


class KLinePoint(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float = 0.0


class StockMeta(BaseModel):
    symbol: str
    name: Optional[str] = None
    is_suspended: Optional[bool] = None
    listing_days: Optional[int] = None
    tags: Optional[list[str]] = None


class SwingSignalRequest(BaseModel):
    meta: StockMeta
    data: list[KLinePoint]


class SwingSignalMetrics(BaseModel):
    ma5: Optional[float] = None
    ma10: Optional[float] = None
    ma20: Optional[float] = None
    ma30: Optional[float] = None
    ma_golden_cross: bool = False
    volume_ratio: Optional[float] = None
    r_value: Optional[float] = None
    pct_change: Optional[float] = None
    latest_close: Optional[float] = None
    yy_pass: Optional[bool] = None
    signal_type: Optional[str] = None
    limitup_breakout: Optional[dict[str, Any]] = None


class SwingSignalResponse(BaseModel):
    should_buy: bool
    score: int
    reasons: list[str]
    suggested_position: float = Field(ge=0.0, le=1.0)
    stop_loss: Optional[float]
    take_profit: Optional[float]
    metrics: SwingSignalMetrics
    signal_type: Optional[str] = None


class ShortTermContext(BaseModel):
    expected_open_pct: float = 0.0
    actual_open_pct: float = 0.0
    promotion_rate: float = 0.0
    limit_up_count: int = 0
    limit_down_count: int = 0
    breadth_pct: float = 0.0
    leading_stock_negative_feedback: bool = False
    intraday_rebound: bool = False
    board_lock: bool = False
    theme_mainline: bool = True
    turnover_rate: Optional[float] = None


class ShortTermSignalRequest(BaseModel):
    meta: StockMeta
    context: ShortTermContext


class ShortTermSignalResponse(BaseModel):
    should_buy: bool
    score: int
    reasons: list[str]
    suggested_position: float = Field(ge=0.0, le=1.0)
    stop_loss_pct: float
    take_profit_min_pct: float
    take_profit_max_pct: float
    risk_flags: list[str]
    sentiment_score: float
    sentiment_label: str


class MarketSentimentRequest(BaseModel):
    promotion_rate: float = 0.0
    limit_up_count: int = 0
    limit_down_count: int = 0
    breadth_pct: float = 0.0
    leading_stock_negative_feedback: bool = False


class MarketSentimentResponse(BaseModel):
    sentiment_score: float
    label: str
    risk_flags: list[str]


class StockScanRequest(BaseModel):
    symbols: list[str]
    start_date: str
    end_date: str
    mode: str = Field(default="swing")
    meta_map: Optional[dict[str, StockMeta]] = None
    short_term_context_map: Optional[dict[str, ShortTermContext]] = None
    max_concurrency: int = Field(default=4, ge=1, le=20)


class StockScanResult(BaseModel):
    symbol: str
    should_buy: bool
    score: int
    reasons: list[str]
    suggested_position: float
    metrics: dict[str, Any] | None = None


class StockScanResponse(BaseModel):
    results: list[StockScanResult]
