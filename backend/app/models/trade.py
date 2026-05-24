from sqlalchemy import DateTime, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    strategy_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True))
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    trade_time: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
