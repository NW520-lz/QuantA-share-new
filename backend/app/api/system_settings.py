import asyncio
from datetime import datetime, timezone
from sqlalchemy import func, text

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.deps import get_current_user
from app.models.position import Position
from app.models.user_setting import UserSetting
from app.schemas.system_overview import SystemOverview
from app.schemas.system_settings import SystemSettingsOut, SystemSettingsPayload, SystemStatus
from app.services.data.baostock import get_all_a_stocks
from app.services.system_log import list_recent_logs, write_system_log

router = APIRouter()


@router.get("/settings", response_model=SystemSettingsOut)
async def get_settings(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> UserSetting:
    result = await db.execute(select(UserSetting).where(UserSetting.user_id == user.id))
    setting = result.scalar_one_or_none()
    if setting is None:
        setting = UserSetting(user_id=user.id, settings={})
        db.add(setting)
        await db.commit()
        await db.refresh(setting)
    return setting


@router.put("/settings", response_model=SystemSettingsOut)
async def update_settings(
    payload: SystemSettingsPayload,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> UserSetting:
    result = await db.execute(select(UserSetting).where(UserSetting.user_id == user.id))
    setting = result.scalar_one_or_none()
    if setting is None:
        setting = UserSetting(user_id=user.id, settings=payload.settings)
        db.add(setting)
    else:
        setting.settings = payload.settings
    await db.commit()
    await db.refresh(setting)
    return setting


@router.get("/status", response_model=SystemStatus)
async def status() -> SystemStatus:
    return SystemStatus(server_time=datetime.now(timezone.utc))


@router.get("/overview", response_model=SystemOverview)
async def overview(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> SystemOverview:
    result = await db.execute(select(UserSetting).where(UserSetting.user_id == user.id))
    setting = result.scalar_one_or_none()
    raw_settings = setting.settings if setting else {}

    # real DB connectivity check
    db_status = "connected"
    db_latency_ms = 0
    try:
        start = datetime.now(timezone.utc)
        await db.execute(text("select 1"))
        db_latency_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
    except Exception:
        db_status = "disconnected"
        db_latency_ms = 999

    baostock_connected = False
    try:
        stocks = await get_all_a_stocks()
        baostock_connected = len(stocks) > 0
    except Exception:
        baostock_connected = False

    positions_count = int(await db.scalar(select(func.count()).select_from(Position).where(Position.user_id == user.id)) or 0)
    logs = await list_recent_logs(db, user_id=str(user.id), channels=["system"], limit=30)
    if not logs:
        await write_system_log(
            db,
            user_id=str(user.id),
            channel="system",
            level="SUCCESS",
            source="system.overview",
            message=f"系统在线，已加载 {positions_count} 条持仓记录",
        )
        await write_system_log(
            db,
            user_id=str(user.id),
            channel="system",
            level="OK" if db_status == "connected" else "WARN",
            source="system.overview",
            message=f"数据库连接状态: {db_status}，延迟 {db_latency_ms}ms",
        )
        await write_system_log(
            db,
            user_id=str(user.id),
            channel="system",
            level="OK" if baostock_connected else "WARN",
            source="system.overview",
            message=f"行情源状态: {'CONNECTED' if baostock_connected else 'DISCONNECTED'}",
        )
        logs = await list_recent_logs(db, user_id=str(user.id), channels=["system"], limit=30)

    overview_logs = [
        {
            "timestamp": item.created_at,
            "level": item.source.upper().replace(".", "_"),
            "message": item.message,
            "status": item.level,
        }
        for item in logs
    ]

    return SystemOverview(
        baostock_connected=baostock_connected,
        db_status=db_status,
        db_latency_ms=db_latency_ms,
        db_storage_gb=float(raw_settings.get("db_storage_gb", 0.0)),
        auto_sync_enabled=bool(raw_settings.get("auto_sync_enabled", True)),
        default_broker=str(raw_settings.get("default_broker", "中信证券 (机构通道)")),
        auto_order_enabled=bool(raw_settings.get("auto_order_enabled", False)),
        risk_agreement_status=str(raw_settings.get("risk_agreement_status", "已完成")),
        risk_agreement_text=str(
            raw_settings.get(
                "risk_agreement_text",
                "已签署《量化程序化交易风险揭示书》，请按月复核。",
            )
        ),
        theme=str(raw_settings.get("theme", "dark")),
        color_mode=str(raw_settings.get("color_mode", "red_up_green_down")),
        version="2.4.0",
        logs=overview_logs,
        settings=raw_settings,
    )


@router.get("/logs")
async def get_logs(
    channel: str = "system",
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> list[dict]:
    channels = [c.strip() for c in channel.split(",") if c.strip()]
    logs = await list_recent_logs(db, user_id=str(user.id), channels=channels or None, limit=limit)
    return [
        {
            "id": str(item.id),
            "timestamp": item.created_at,
            "channel": item.channel,
            "level": item.level,
            "source": item.source,
            "message": item.message,
            "context": item.context or {},
        }
        for item in logs
    ]


@router.get("/heartbeat")
async def heartbeat() -> StreamingResponse:
    async def event_stream():
        while True:
            now = datetime.now(timezone.utc).isoformat()
            yield f"data: {now}\n\n"
            await asyncio.sleep(5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
