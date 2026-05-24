from datetime import datetime
from typing import Any

from pydantic import BaseModel


class SystemLogItem(BaseModel):
    timestamp: datetime
    level: str
    message: str
    status: str


class SystemOverview(BaseModel):
    baostock_connected: bool
    db_status: str
    db_latency_ms: int
    db_storage_gb: float
    auto_sync_enabled: bool
    default_broker: str
    auto_order_enabled: bool
    risk_agreement_status: str
    risk_agreement_text: str
    theme: str
    color_mode: str
    version: str
    logs: list[SystemLogItem]
    settings: dict[str, Any]
