import asyncio
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.deps import get_current_user
from app.services.data.baostock import get_all_a_stocks, get_daily_data
from app.services.skills.backtest_runner import run_backtest_skill
from app.services.skills.risk_database import run_risk_screening
from app.services.skills.trend_filter import run_trend_filter
from app.services.skills.volume_analyzer import run_volume_analyzer

router = APIRouter()


class BatchSkillRequest(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=20)
    start_date: str = "2024-01-01"
    end_date: str = ""


class BacktestSkillRequest(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=5)
    start_date: str = "2024-01-01"
    end_date: str = ""
    lookback_days: int = 60
    hold_days: int = 10
    stop_loss_pct: float = 0.05
    take_profit_pct: float = 0.08


@router.post("/skills/trend-filter")
async def trend_filter_skill(
    req: BatchSkillRequest, user=Depends(get_current_user)
) -> list[dict]:
    end = req.end_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    results = []
    for symbol in req.symbols:
        try:
            data = await get_daily_data(symbol, req.start_date, end)
            meta = {"symbol": symbol, "name": "", "listing_days": 9999}
            result = run_trend_filter(data, meta)
            results.append(result)
        except Exception as exc:
            results.append(
                {
                    "symbol": symbol,
                    "error": str(exc),
                    "trend_direction": "unknown",
                    "score": 0,
                }
            )
    return results


@router.post("/skills/volume-analyzer")
async def volume_analyzer_skill(
    req: BatchSkillRequest, user=Depends(get_current_user)
) -> list[dict]:
    end = req.end_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    results = []
    for symbol in req.symbols:
        try:
            data = await get_daily_data(symbol, req.start_date, end)
            meta = {"symbol": symbol, "name": ""}
            result = run_volume_analyzer(data, meta)
            results.append(result)
        except Exception as exc:
            results.append(
                {
                    "symbol": symbol,
                    "error": str(exc),
                    "volume_state": "unknown",
                    "volume_score": 0,
                }
            )
    return results


@router.post("/skills/risk-screening")
async def risk_screening_skill(
    req: BatchSkillRequest, user=Depends(get_current_user)
) -> list[dict]:
    end = req.end_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    results = []
    for symbol in req.symbols:
        try:
            data = await get_daily_data(symbol, req.start_date, end)
            meta = {"symbol": symbol, "name": "", "listing_days": 9999}
            result = run_risk_screening(data, meta)
            results.append(result)
        except Exception as exc:
            results.append(
                {
                    "symbol": symbol,
                    "error": str(exc),
                    "risk_level": "unknown",
                    "risk_score": 0,
                }
            )
    return results


@router.post("/skills/backtest")
async def backtest_skill(
    req: BacktestSkillRequest, user=Depends(get_current_user)
) -> list[dict]:
    results = []
    for symbol in req.symbols:
        try:
            result = await run_backtest_skill(
                symbol=symbol,
                start_date=req.start_date,
                end_date=req.end_date,
                lookback_days=req.lookback_days,
                hold_days=req.hold_days,
                stop_loss_pct=req.stop_loss_pct,
                take_profit_pct=req.take_profit_pct,
            )
            results.append(result)
        except Exception as exc:
            results.append({"symbol": symbol, "error": str(exc), "total_trades": 0})
    return results


@router.post("/skills/full-scan")
async def full_scan_skill(
    max_symbols: int = Query(default=10, le=50),
    start_date: str = Query(default="2024-01-01"),
    end_date: str = Query(default=""),
    user=Depends(get_current_user),
) -> dict:
    end = end_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    stocks = await get_all_a_stocks()
    stocks = stocks[:max_symbols]

    results = []

    async def _evaluate(s: dict) -> dict:
        try:
            data = await get_daily_data(s["symbol"], start_date, end)
            meta = {"symbol": s["symbol"], "name": s["name"], "listing_days": 9999}
            trend = run_trend_filter(data, meta)
            volume = run_volume_analyzer(data, meta)
            risk = run_risk_screening(data, meta)

            trend_score = max(0, trend.get("score", 0))
            volume_score = max(0, volume.get("volume_score", 0))
            risk_score = max(0, risk.get("risk_score", 0))
            composite = trend_score * 2 + volume_score * 1.5 - risk_score * 1.2

            return {
                "symbol": s["symbol"],
                "name": s["name"],
                "trend": {
                    "direction": trend.get("trend_direction"),
                    "score": trend.get("score"),
                    "ma_state": trend.get("ma_state"),
                },
                "volume": {
                    "state": volume.get("volume_state"),
                    "score": volume.get("volume_score"),
                    "vol_ratio_20": volume.get("vol_ratio_20"),
                },
                "risk": {
                    "level": risk.get("risk_level"),
                    "score": risk.get("risk_score"),
                },
                "composite_score": round(composite, 1),
            }
        except Exception:
            return {"symbol": s["symbol"], "name": s["name"], "error": "fetch_failed"}

    sem = asyncio.Semaphore(8)
    async with sem:
        tasks = [_evaluate(s) for s in stocks]
        results = await asyncio.gather(*tasks)

    valid = [r for r in results if "error" not in r]
    ranked = sorted(valid, key=lambda x: x.get("composite_score", 0), reverse=True)

    buy_signals = [
        r
        for r in ranked
        if r.get("trend", {}).get("direction") in ("strong_bull", "bull")
        and r.get("risk", {}).get("level") in ("low", "medium")
        and r.get("composite_score", 0) > 5
    ]

    return {
        "total_scanned": len(stocks),
        "valid_results": len(valid),
        "buy_candidates": len(buy_signals),
        "top_picks": ranked[:10],
        "buy_signals": buy_signals[:10],
    }
