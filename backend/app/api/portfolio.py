from datetime import datetime, timezone
import csv
import io
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.deps import get_current_user
from app.models.position import Position
from app.models.scan_result import ScanResult
from app.schemas.portfolio import RiskRequest, RiskResponse
from app.schemas.portfolio import PortfolioDashboard
from app.schemas.position import PositionOut, PositionUpsert
from app.services.risk.calculator import calculate_risk

logger = logging.getLogger("portfolio")
router = APIRouter()


@router.get("/positions", response_model=list[PositionOut])
async def list_positions(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> list[Position]:
    result = await db.execute(select(Position).where(Position.user_id == user.id))
    return list(result.scalars().all())


@router.post("/positions", response_model=PositionOut)
async def upsert_position(
    payload: PositionUpsert,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> Position:
    try:
        symbol_key = payload.symbol.strip().lower()
        result = await db.execute(
            select(Position).where(
                Position.user_id == user.id, Position.symbol == symbol_key
            )
        )
        position = result.scalar_one_or_none()

        avg_price = float(payload.avg_price)
        quantity = float(payload.quantity)
        last_price = (
            float(payload.last_price) if payload.last_price is not None else avg_price
        )
        pnl = (last_price - avg_price) * quantity
        pnl_pct = ((last_price - avg_price) / avg_price * 100) if avg_price > 0 else 0.0

        if position is None:
            position = Position(
                user_id=user.id,
                symbol=symbol_key,
                name=payload.name,
                quantity=quantity,
                avg_price=avg_price,
                last_price=last_price,
                pnl=pnl,
                pnl_pct=round(pnl_pct, 4),
                risk_level=payload.risk_level,
            )
            db.add(position)
        else:
            position.name = payload.name or position.name
            position.quantity = quantity
            position.avg_price = avg_price
            position.last_price = last_price
            position.pnl = pnl
            position.pnl_pct = round(pnl_pct, 4)
            if payload.risk_level is not None:
                position.risk_level = payload.risk_level

        await db.commit()
        await db.refresh(position)
        return position
    except Exception as exc:
        logger.error(f"Position upsert failed: {exc}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/risk", response_model=RiskResponse)
async def risk_calculation(
    payload: RiskRequest,
    user=Depends(get_current_user),
) -> RiskResponse:
    result = calculate_risk(payload.model_dump())
    return RiskResponse(**result)


@router.get("/balance")
async def wallet_balance(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    positions = list(
        (await db.execute(select(Position).where(Position.user_id == user.id)))
        .scalars()
        .all()
    )
    total_market_value = 0.0
    total_pnl = 0.0
    for p in positions:
        qty = float(p.quantity or 0)
        px = float(p.last_price or p.avg_price or 0)
        total_market_value += qty * px
        total_pnl += float(p.pnl or 0)

    return {
        "total_positions": len(positions),
        "total_market_value": round(total_market_value, 2),
        "total_pnl": round(total_pnl, 2),
        "positions_detail": [
            {
                "symbol": p.symbol,
                "name": p.name,
                "quantity": float(p.quantity or 0),
                "avg_price": float(p.avg_price or 0),
                "last_price": float(p.last_price or 0),
                "market_value": round(
                    float(p.quantity or 0) * float(p.last_price or p.avg_price or 0), 2
                ),
                "pnl": round(float(p.pnl or 0), 2),
                "pnl_pct": round(float(p.pnl_pct or 0), 2),
            }
            for p in positions
        ],
    }


@router.post("/clear-all")
async def clear_all_positions(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    result = await db.execute(delete(Position).where(Position.user_id == user.id))
    await db.commit()
    deleted = result.rowcount
    logger.info(f"User {user.id} cleared {deleted} positions")
    return {"cleared": deleted, "message": f"已清仓 {deleted} 只持仓"}


@router.get("/export")
async def export_positions(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    positions = list(
        (
            await db.execute(
                select(Position)
                .where(Position.user_id == user.id)
                .order_by(Position.updated_at.desc())
            )
        )
        .scalars()
        .all()
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["代码", "名称", "数量", "均价", "现价", "市值", "盈亏", "盈亏%", "风险等级"]
    )
    for p in positions:
        writer.writerow(
            [
                p.symbol,
                p.name or "",
                float(p.quantity or 0),
                float(p.avg_price or 0),
                float(p.last_price or 0),
                round(
                    float(p.quantity or 0) * float(p.last_price or p.avg_price or 0), 2
                ),
                round(float(p.pnl or 0), 2),
                f"{round(float(p.pnl_pct or 0), 2)}%",
                p.risk_level or "",
            ]
        )
    output.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=positions_{timestamp}.csv"
        },
    )


@router.get("/dashboard", response_model=PortfolioDashboard)
async def dashboard(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> PortfolioDashboard:
    positions = list(
        (
            await db.execute(
                select(Position)
                .where(Position.user_id == user.id)
                .order_by(Position.updated_at.desc())
            )
        )
        .scalars()
        .all()
    )
    scans = list(
        (
            await db.execute(
                select(ScanResult)
                .order_by(ScanResult.score.desc(), ScanResult.scanned_at.desc())
                .limit(15)
            )
        )
        .scalars()
        .all()
    )

    position_values = []
    for p in positions:
        qty = float(p.quantity or 0)
        px = float(p.last_price or p.avg_price or 0)
        value = max(0.0, qty * px)
        position_values.append((p, value))

    total_value = sum(v for _, v in position_values)
    assumed_equity = total_value / 0.742 if total_value > 0 else 1.0
    total_position_pct = min(
        100.0, (total_value / assumed_equity) * 100 if assumed_equity > 0 else 0.0
    )
    max_single_pct = 0.0
    if total_value > 0:
        max_single_pct = max((v / total_value) * 100 for _, v in position_values)

    beta = 1.0
    max_drawdown = 0.0
    if total_value > 0:
        pnl_values = [float(p.pnl or 0) for p, _ in position_values]
        neg_pnl = sum(abs(v) for v in pnl_values if v < 0)
        max_drawdown = (
            min(100.0, (neg_pnl / total_value) * 100) if total_value > 0 else 0.0
        )

    high = sum(
        v
        for p, v in position_values
        if (p.risk_level or "").lower() in {"high", "高", "high_risk"}
    )
    medium = sum(
        v
        for p, v in position_values
        if (p.risk_level or "").lower() in {"medium", "中", "mid"}
    )
    low = sum(
        v
        for p, v in position_values
        if (p.risk_level or "").lower() in {"low", "低", "low_risk"}
    )
    unknown = max(0.0, total_value - high - medium - low)
    cash = max(0.0, assumed_equity - total_value)

    def _pct(v: float) -> float:
        return round((v / assumed_equity) * 100, 2) if assumed_equity > 0 else 0.0

    allocation = [
        {"name": "高风险仓位", "value_pct": _pct(high)},
        {"name": "中风险仓位", "value_pct": _pct(medium)},
        {"name": "低风险仓位", "value_pct": _pct(low + unknown)},
        {"name": "现金", "value_pct": _pct(cash)},
    ]

    risk_hint = "风险敞口在可控范围内。"
    if max_drawdown >= 5:
        risk_hint = "组合回撤偏高，建议先降杠杆并收缩高风险仓位。"
    elif max_single_pct >= 20:
        risk_hint = "单一标的集中度偏高，建议分散仓位。"

    candidates = []
    for s in scans:
        if not s.should_buy:
            continue
        tp = float(s.price) * 1.12 if s.price else 0.0
        candidates.append(
            {
                "symbol": s.symbol.upper(),
                "name": s.name,
                "price": float(s.price),
                "stop_loss": float(s.stop_loss),
                "take_profit": float(tp),
                "risk_pct": max(
                    0.0,
                    ((float(s.price) - float(s.stop_loss)) / float(s.price) * 100)
                    if s.price
                    else 0.0,
                ),
                "tag": "高胜率"
                if s.should_buy
                else ("趋势观察" if s.status == "yellow" else "谨慎"),
            }
        )
        if len(candidates) >= 5:
            break

    return PortfolioDashboard(
        updated_at=datetime.now(timezone.utc).isoformat(),
        candidates=candidates,
        positions=[
            {
                "symbol": p.symbol,
                "name": p.name,
                "quantity": float(p.quantity or 0),
                "avg_price": float(p.avg_price or 0),
                "last_price": float(p.last_price or 0),
                "pnl_pct": float(p.pnl_pct or 0),
                "pnl": float(p.pnl or 0),
                "risk_level": p.risk_level or "",
            }
            for p in positions
        ],
        total_position_pct=round(total_position_pct, 2),
        allocation=allocation,
        max_single_position_pct=round(max_single_pct, 2),
        beta=round(beta, 2),
        max_drawdown_pct=round(max_drawdown, 2),
        risk_hint=risk_hint,
    )
