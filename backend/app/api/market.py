import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.deps import get_current_user
from app.models.review_log import ReviewLog
from app.models.scan_result import ScanResult
from app.models.user_setting import UserSetting
from app.schemas.market import MarketCandidatesResponse
from app.services.data.baostock import get_all_a_stocks, get_daily_data
from app.services.system_log import write_system_log
from app.services.strategy.backtest import run_swing_backtest
from app.services.strategy.short_term import evaluate_market_sentiment
from app.services.strategy.swing import evaluate_swing_signal

router = APIRouter()

MAX_CONCURRENT = 15


class BatchBacktestRequest(BaseModel):
    symbols: list[str] = []
    start_date: str = "2024-01-01"
    end_date: str = ""
    lookback_days: int = 60
    hold_days: int = 10
    stop_loss_pct: float = 0.05
    take_profit_pct: float = 0.08
    scan_all: bool = False
    max_symbols: int = 500


class IndustryExclusionsPayload(BaseModel):
    industries: list[str] = []


SYMBOLS = [
    ("sh.600519", "Kweichow Moutai"),
    ("sz.000001", "Ping An Bank"),
    ("sh.601318", "Ping An Insurance"),
    ("sz.300750", "CATL"),
    ("sz.000858", "Wuliangye"),
]


def _display_symbol(symbol: str) -> str:
    market, code = symbol.split(".")
    return f"{code.upper()}.{market.upper()}"


def _build_bars(closes: list[float]) -> list[int]:
    if not closes:
        return [50, 50, 50, 50, 50]
    low = min(closes)
    high = max(closes)
    if high <= low:
        return [60 for _ in closes]
    return [max(20, min(95, int(20 + ((c - low) / (high - low)) * 75))) for c in closes]


@router.get("/a-stocks")
async def list_a_stocks() -> list[dict]:
    stocks = await get_all_a_stocks()
    return stocks


@router.get("/scan-status")
async def scan_status(db: AsyncSession = Depends(get_db)) -> dict:
    count = await db.scalar(
        select(func.count()).select_from(select(ScanResult).subquery())
    )
    latest = await db.execute(
        select(ScanResult.scanned_at).order_by(ScanResult.scanned_at.desc()).limit(1)
    )
    latest_time = latest.scalar()
    return {
        "total_scanned": count or 0,
        "last_scan_at": latest_time.isoformat() if latest_time else None,
    }


@router.get("/candidates", response_model=MarketCandidatesResponse)
async def get_candidates(
    db: AsyncSession = Depends(get_db),
) -> MarketCandidatesResponse:
    result = await db.execute(
        select(ScanResult).order_by(
            ScanResult.score.desc(), ScanResult.should_buy.desc()
        )
    )
    rows = result.scalars().all()

    if not rows:
        return MarketCandidatesResponse(
            progress_pct=0,
            sentiment_label="扫描中",
            sentiment_score=0.0,
            candidates=[],
            watchlist=[],
        )

    candidates = []
    watchlist = []
    for row in rows:
        candidates.append(
            {
                "symbol": _display_symbol(row.symbol),
                "name": row.name,
                "price": row.price,
                "stop_loss": row.stop_loss,
                "r_value": row.r_value,
                "volume_ratio": row.volume_ratio,
                "status": row.status,
                "should_buy": row.should_buy,
                "signal_type": row.signal_type,
            }
        )
        if len(watchlist) < 3:
            bars = [int(b) for b in (row.bars.split(",")[:5] if row.bars else [])] or [
                50
            ] * 5
            watchlist.append(
                {
                    "title": f"{row.name} ({row.symbol.split('.')[-1] if '.' in row.symbol else row.symbol})",
                    "change_pct": row.change_pct,
                    "bars": bars,
                }
            )

    buy_count = sum(1 for c in candidates if c["should_buy"])
    # 有信号的标的数（绿色+黄色），用于市场广度计算
    signal_count = sum(1 for c in candidates if c["status"] in ("green", "yellow"))
    # 综合推广率：买入信号占30%权重，有信号标点占70%权重
    buy_rate = buy_count / len(candidates) if candidates else 0.0
    signal_rate = signal_count / len(candidates) if candidates else 0.0
    promotion_rate = buy_rate * 0.3 + signal_rate * 0.7
    sentiment = evaluate_market_sentiment(
        {
            "promotion_rate": promotion_rate,
            "limit_up_count": buy_count,
            "limit_down_count": max(0, len(candidates) - signal_count),
            "breadth_pct": signal_rate,
            "leading_stock_negative_feedback": False,
        }
    )
    progress_pct = min(100, max(0, int(45 + promotion_rate * 55)))

    return MarketCandidatesResponse(
        progress_pct=progress_pct,
        sentiment_label=str(sentiment["label"]),
        sentiment_score=float(sentiment["sentiment_score"]),
        candidates=candidates,
        watchlist=watchlist,
    )


@router.get("/strategy-panel")
async def strategy_panel(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    user_setting_result = await db.execute(
        select(UserSetting).where(UserSetting.user_id == user.id)
    )
    setting = user_setting_result.scalar_one_or_none()
    raw_settings = setting.settings if setting else {}
    industry_exclusions = raw_settings.get("industry_exclusions", ["银行业", "地产业"])

    scans = list(
        (
            await db.execute(
                select(ScanResult).order_by(
                    ScanResult.score.desc(), ScanResult.scanned_at.desc()
                )
            )
        )
        .scalars()
        .all()
    )
    total_pool = len(scans)
    buy_count = sum(1 for s in scans if s.should_buy)
    bullish_pct = round((buy_count / total_pool) * 100, 1) if total_pool else 0.0

    history_result = await db.execute(
        select(ReviewLog)
        .where(
            ReviewLog.user_id == user.id,
            ReviewLog.extra_data["type"].astext == "backtest",
        )
        .order_by(ReviewLog.created_at.desc())
        .limit(20)
    )
    history = history_result.scalars().all()

    weighted_trades = 0
    weighted_wins = 0
    daily_trades: list[float] = []
    for log in history:
        meta = log.extra_data or {}
        total_trades = int(meta.get("total_trades") or 0)
        total_wins = int(meta.get("total_wins") or 0)
        weighted_trades += total_trades
        weighted_wins += total_wins

        start_date = meta.get("start_date")
        end_date = meta.get("end_date")
        days = 1
        try:
            if start_date and end_date:
                s = datetime.strptime(start_date, "%Y-%m-%d").date()
                e = datetime.strptime(end_date, "%Y-%m-%d").date()
                days = max(1, (e - s).days + 1)
        except Exception:
            days = 1
        if total_trades > 0:
            daily_trades.append(total_trades / days)

    history_win_rate = (
        round((weighted_wins / weighted_trades) * 100, 1) if weighted_trades else 0.0
    )
    daily_mean = sum(daily_trades) / len(daily_trades) if daily_trades else 0.0
    trade_min = max(0, int(daily_mean * 0.8))
    trade_max = max(trade_min, int(daily_mean * 1.2))

    db_latency_ms = 0
    try:
        start = datetime.now(timezone.utc)
        await db.execute(text("select 1"))
        db_latency_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
    except Exception:
        db_latency_ms = 999

    return {
        "industry_exclusions": industry_exclusions,
        "estimated_daily_trades_min": trade_min,
        "estimated_daily_trades_max": trade_max,
        "bullish_pct": bullish_pct,
        "history_win_rate": history_win_rate,
        "engine_latency_ms": db_latency_ms,
        "pool_sample_count": total_pool,
    }


@router.put("/strategy-panel/industry-exclusions")
async def update_industry_exclusions(
    payload: IndustryExclusionsPayload,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    result = await db.execute(select(UserSetting).where(UserSetting.user_id == user.id))
    setting = result.scalar_one_or_none()
    settings_data = dict(setting.settings or {}) if setting else {}
    normalized = sorted({s.strip() for s in payload.industries if s and s.strip()})
    settings_data["industry_exclusions"] = normalized

    if setting is None:
        setting = UserSetting(user_id=user.id, settings=settings_data)
        db.add(setting)
    else:
        setting.settings = settings_data

    await db.commit()
    await write_system_log(
        db,
        user_id=str(user.id),
        channel="system",
        level="INFO",
        source="strategy.panel",
        message=f"行业规避名单已更新，共 {len(normalized)} 个行业",
    )
    return {"industry_exclusions": normalized}


@router.get("/backtest/swing")
async def swing_backtest(
    symbol: str = "sh.600519",
    start_date: str = "2024-01-01",
    end_date: str = "2026-05-20",
) -> dict:
    try:
        return await run_swing_backtest(
            symbol=symbol, start_date=start_date, end_date=end_date
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Backtest failed: {exc}") from exc


@router.post("/backtest/batch")
async def batch_backtest(
    req: BatchBacktestRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    end = req.end_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if req.scan_all:
        stocks = await _resolve_symbols(req)
    elif req.symbols:
        stocks = req.symbols
    else:
        stocks = [s[0] for s in SYMBOLS]

    if not stocks:
        raise HTTPException(status_code=400, detail="No symbols to backtest")

    await write_system_log(
        db,
        user_id=str(user.id),
        channel="review",
        level="INFO",
        source="market.backtest",
        message=f"开始批量回测，标的数={len(stocks)}，模式={'全A' if req.scan_all else '自选'}",
        context={"start_date": req.start_date, "end_date": end},
    )

    sem = asyncio.Semaphore(MAX_CONCURRENT)

    async def _run(symbol: str) -> dict:
        async with sem:
            try:
                result = await run_swing_backtest(
                    symbol=symbol,
                    start_date=req.start_date,
                    end_date=end,
                    lookback_days=req.lookback_days,
                    hold_days=req.hold_days,
                    stop_loss_pct=req.stop_loss_pct,
                    take_profit_pct=req.take_profit_pct,
                )
                return result
            except Exception as exc:
                return {
                    "symbol": symbol,
                    "error": str(exc),
                    "trades": 0,
                    "wins": 0,
                    "win_rate": 0.0,
                    "avg_return_pct": 0.0,
                    "samples": [],
                }

    results = await asyncio.gather(*[_run(s) for s in stocks])

    total_trades = sum(r.get("trades", 0) for r in results)
    total_wins = sum(r.get("wins", 0) for r in results)
    total_win_rate = (total_wins / total_trades * 100) if total_trades else 0.0
    valid = [r for r in results if r.get("trades", 0) > 0]
    avg_return = (
        sum(r.get("avg_return_pct", 0.0) for r in valid) / len(valid) if valid else 0.0
    )
    error_count = sum(1 for r in results if r.get("error"))
    symbol_count = len(stocks)

    result_list = []
    for r in results:
        item = {
            "symbol": r.get("symbol"),
            "trades": r.get("trades", 0),
            "wins": r.get("wins", 0),
            "win_rate": round(r.get("win_rate", 0) * 100, 2)
            if r.get("win_rate")
            else 0.0,
            "avg_return_pct": round(r.get("avg_return_pct", 0) * 100, 2),
        }
        if r.get("error"):
            item["error"] = str(r["error"])[:200]
        result_list.append(item)

    top_win = sorted(
        [r for r in result_list if r["trades"] > 0],
        key=lambda x: x["win_rate"],
        reverse=True,
    )[:10]
    top_return = sorted(
        [r for r in result_list if r["trades"] > 0],
        key=lambda x: x["avg_return_pct"],
        reverse=True,
    )[:10]

    summary = {
        "type": "backtest",
        "scan_mode": "all" if req.scan_all else "custom",
        "total_symbols": symbol_count,
        "total_trades": total_trades,
        "total_wins": total_wins,
        "total_win_rate": round(total_win_rate, 2),
        "avg_return_pct": round(avg_return * 100, 2),
        "start_date": req.start_date,
        "end_date": end,
        "lookback_days": req.lookback_days,
        "hold_days": req.hold_days,
        "stop_loss_pct": req.stop_loss_pct * 100,
        "take_profit_pct": req.take_profit_pct * 100,
        "error_count": error_count,
        "valid_symbols": len(valid),
        "top_win": top_win,
        "top_return": top_return,
        "results": result_list,
    }

    content_parts = [
        f"标的数: {symbol_count}",
        f"总交易: {total_trades}",
        f"胜率: {total_win_rate:.1f}%",
        f"均收益: {avg_return * 100:.2f}%",
        f"有效标的: {len(valid)}",
    ]
    if req.scan_all:
        content_parts.append(f"扫描模式: 全A股({req.max_symbols}只)")

    log = ReviewLog(
        user_id=user.id,
        log_date=date.today(),
        title=f"批量回测 {req.start_date} ~ {end}"
        + (" [全A扫描]" if req.scan_all else ""),
        content=" | ".join(content_parts),
        extra_data=summary,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    await write_system_log(
        db,
        user_id=str(user.id),
        channel="review",
        level="SUCCESS",
        source="market.backtest",
        message=f"批量回测完成，胜率={total_win_rate:.1f}%，有效标的={len(valid)}",
        context={"log_id": str(log.id)},
    )

    return {"summary": summary, "log_id": str(log.id)}


@router.get("/backtest/history")
async def backtest_history(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> list[dict]:
    result = await db.execute(
        select(ReviewLog)
        .where(
            ReviewLog.user_id == user.id,
            ReviewLog.extra_data["type"].astext == "backtest",
        )
        .order_by(ReviewLog.created_at.desc())
    )
    logs = result.scalars().all()
    return [
        {
            "id": str(log.id),
            "log_date": log.log_date.isoformat() if log.log_date else None,
            "title": log.title,
            "content": log.content,
            "metadata": log.extra_data,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]


async def _resolve_symbols(req: BatchBacktestRequest) -> list[str]:
    all_stocks = await get_all_a_stocks()
    all_stocks = all_stocks[: req.max_symbols]
    unique = set()
    symbols = []
    for s in all_stocks:
        key = s["symbol"]
        if key not in unique:
            unique.add(key)
            symbols.append(key)
    return symbols
