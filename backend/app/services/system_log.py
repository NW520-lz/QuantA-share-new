from collections.abc import Sequence

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_event_log import SystemEventLog


async def write_system_log(
    db: AsyncSession,
    *,
    user_id: str | None,
    message: str,
    channel: str = "system",
    level: str = "INFO",
    source: str = "backend",
    context: dict | None = None,
) -> None:
    log = SystemEventLog(
        user_id=user_id,
        message=message,
        channel=channel,
        level=level,
        source=source,
        context=context or {},
    )
    db.add(log)
    await db.commit()


async def list_recent_logs(
    db: AsyncSession,
    *,
    user_id: str,
    channels: Sequence[str] | None = None,
    limit: int = 50,
) -> list[SystemEventLog]:
    stmt: Select = (
        select(SystemEventLog)
        .where((SystemEventLog.user_id == user_id) | (SystemEventLog.user_id.is_(None)))
        .order_by(SystemEventLog.created_at.desc())
        .limit(max(1, min(limit, 200)))
    )
    if channels:
        stmt = stmt.where(SystemEventLog.channel.in_(list(channels)))

    result = await db.execute(stmt)
    return list(result.scalars().all())
