from sqlalchemy import Boolean, DateTime, Float, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ScanResult(Base):
    __tablename__ = "scan_results"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    r_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    volume_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="red")
    should_buy: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    change_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    bars: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    signal_type: Mapped[str | None] = mapped_column(
        String(32), nullable=True, default=None
    )
    scanned_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), index=True
    )
