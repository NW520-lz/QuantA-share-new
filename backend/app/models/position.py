from sqlalchemy import DateTime, ForeignKey, Numeric, String, text, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint("user_id", "symbol", name="uq_positions_user_symbol"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str | None] = mapped_column(String(200))
    quantity: Mapped[float] = mapped_column(
        Numeric(20, 4), nullable=False, server_default=text("0.0")
    )
    avg_price: Mapped[float | None] = mapped_column(Numeric(20, 4))
    last_price: Mapped[float | None] = mapped_column(Numeric(20, 4))
    pnl: Mapped[float | None] = mapped_column(Numeric(20, 4))
    pnl_pct: Mapped[float | None] = mapped_column(Numeric(12, 4))
    risk_level: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=func.now()
    )
