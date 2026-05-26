from sqlalchemy import DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    plan_code: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'pending'"), index=True)
    starts_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    ends_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
