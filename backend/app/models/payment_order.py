from sqlalchemy import DateTime, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PaymentOrder(Base):
    __tablename__ = "payment_orders"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    plan_code: Mapped[str] = mapped_column(String(64), nullable=False)
    amount_cny: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'pending'"))
    gateway: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'manual'"))
    payment_url: Mapped[str | None] = mapped_column(String(500))
    extra: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    paid_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
