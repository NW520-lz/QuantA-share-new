from sqlalchemy import DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SystemEventLog(Base):
    __tablename__ = "system_event_logs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'system'"))
    level: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'INFO'"))
    source: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'backend'"))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
