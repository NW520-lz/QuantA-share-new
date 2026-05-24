import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.database import AsyncSessionLocal
from app.models.scan_result import ScanResult
from app.services.data.baostock import get_all_a_stocks, get_daily_data
from app.services.strategy.swing import evaluate_swing_signal

logger = logging.getLogger("scanner")

BATCH_SIZE = 50
CONCURRENT = 8
PAUSE_BETWEEN_BATCHES = 0
SCAN_INTERVAL_HOURS = 2
DAYS_LOOKBACK = 90


async def run_full_scan():
    logger.info("Full stock scan starting...")
    start_time = datetime.now(timezone.utc)

    all_stocks = await get_all_a_stocks()
    total = len(all_stocks)
    logger.info(f"Total stocks to scan: {total}")

    end_dt = datetime.now(timezone.utc).date()
    start_dt = end_dt - timedelta(days=DAYS_LOOKBACK)
    start_s = start_dt.strftime("%Y-%m-%d")
    end_s = end_dt.strftime("%Y-%m-%d")

    scanned = 0
    sem = asyncio.Semaphore(CONCURRENT)

    async def _scan_one(stock: dict) -> dict | None:
        symbol = stock["symbol"]
        name = stock["name"]
        market_cap = stock.get("market_cap_billion")
        industry = stock.get("industry")
        async with sem:
            try:
                data = await get_daily_data(symbol, start_s, end_s)
            except Exception:
                return None
        if not data or len(data) < 30:
            return None
        try:
            signal = evaluate_swing_signal(
                data,
                meta={
                    "symbol": symbol,
                    "name": name,
                    "listing_days": 9999,
                    "market_cap_billion": market_cap,
                    "industry": industry,
                },
            )
        except Exception:
            return None
        latest = data[-1]
        close = float(latest["close"])
        stop_loss = float(signal.get("stop_loss") or close * 0.95)
        score = int(signal.get("score", 0))
        signal_type = signal.get("signal_type")
        # 绿 = 极严格涨停预测（量比>=2.5 + R>=0.8 + 多因子共振）
        # 黄 = 有潜力但不完全满足严标准
        # 红 = 不符合
        status = (
            "green" if signal.get("should_buy") else "yellow" if score >= 4 else "red"
        )
        recent = data[-5:]
        change = 0.0
        if len(recent) >= 2 and float(recent[0]["close"]) > 0:
            change = (
                (float(recent[-1]["close"]) - float(recent[0]["close"]))
                / float(recent[0]["close"])
            ) * 100
        r_closes = [r["close"] for r in recent]
        r_min = min(r_closes)
        r_max = max(r_closes)
        span = r_max - r_min if r_max > r_min else 1
        bars = ",".join(
            str(max(20, min(95, int(20 + ((c - r_min) / span * 75))))) for c in r_closes
        )

        return {
            "symbol": symbol,
            "name": name,
            "price": close,
            "stop_loss": stop_loss,
            "r_value": float(signal.get("metrics", {}).get("r_value") or 0.0),
            "volume_ratio": float(signal.get("metrics", {}).get("volume_ratio") or 0.0),
            "status": status,
            "should_buy": signal.get("should_buy", False),
            "score": score,
            "change_pct": change,
            "bars": bars,
            "signal_type": signal_type,
        }

    for idx in range(0, total, BATCH_SIZE):
        batch = all_stocks[idx : idx + BATCH_SIZE]
        results = await asyncio.gather(
            *[_scan_one(s) for s in batch], return_exceptions=True
        )
        valid = [r for r in results if isinstance(r, dict)]

        if valid:
            async with AsyncSessionLocal() as db:
                stmt = pg_insert(ScanResult).values(valid)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["symbol"],
                    set_={
                        "name": stmt.excluded.name,
                        "price": stmt.excluded.price,
                        "stop_loss": stmt.excluded.stop_loss,
                        "r_value": stmt.excluded.r_value,
                        "volume_ratio": stmt.excluded.volume_ratio,
                        "status": stmt.excluded.status,
                        "should_buy": stmt.excluded.should_buy,
                        "score": stmt.excluded.score,
                        "change_pct": stmt.excluded.change_pct,
                        "bars": stmt.excluded.bars,
                        "signal_type": stmt.excluded.signal_type,
                        "scanned_at": func.now(),
                    },
                )
                await db.execute(stmt)
                await db.commit()

        scanned += len(batch)
        logger.info(f"Scanned {scanned}/{total} | valid: {len(valid)}")

        if idx + BATCH_SIZE < total:
            await asyncio.sleep(PAUSE_BETWEEN_BATCHES)

    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info(f"Full scan done in {elapsed:.0f}s, {total} stocks.")


async def scan_loop():
    logger.info("Scanner loop started, first run in 3 seconds...")
    await asyncio.sleep(3)
    while True:
        try:
            await run_full_scan()
        except Exception as exc:
            logger.error(f"Scan failed: {exc}", exc_info=True)
        logger.info(f"Next scan in {SCAN_INTERVAL_HOURS} hours")
        await asyncio.sleep(SCAN_INTERVAL_HOURS * 3600)
