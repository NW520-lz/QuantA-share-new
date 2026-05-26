import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.database import AsyncSessionLocal
from app.models.scan_result import ScanResult
from app.services.data.baostock import get_all_a_stocks, get_batch_daily_data
from app.services.strategy.swing import evaluate_swing_signal

logger = logging.getLogger("scanner")

BATCH_SIZE = 200
SUB_BATCH_SIZE = 50
CONCURRENT = 5
PAUSE_BETWEEN_BATCHES = 0
SCAN_INTERVAL_HOURS = 2
DAYS_LOOKBACK = 90


async def run_full_scan():
    logger.info("Full stock scan starting (akshare mode)...")
    start_time = datetime.now(timezone.utc)

    all_stocks = await get_all_a_stocks()
    total = len(all_stocks)
    logger.info(
        f"Total stocks to scan: {total} | BATCH={BATCH_SIZE} CONCURRENT={CONCURRENT} SUB_BATCH={SUB_BATCH_SIZE}"
    )

    end_dt = datetime.now(timezone.utc).date()
    start_dt = end_dt - timedelta(days=DAYS_LOOKBACK)
    start_s = start_dt.strftime("%Y-%m-%d")
    end_s = end_dt.strftime("%Y-%m-%d")

    scanned = 0
    sem = asyncio.Semaphore(CONCURRENT)

    async def _scan_sub_batch(
        symbols: list[str],
        stock_map: dict[str, dict],
        start_s: str,
        end_s: str,
        sem: asyncio.Semaphore,
    ) -> list[dict | None]:
        async with sem:
            raw_data = {}
            for attempt in range(3):
                try:
                    raw_data = await get_batch_daily_data(symbols, start_s, end_s)
                    if raw_data:
                        break
                except Exception as e:
                    logger.warning(f"Batch fetch attempt {attempt + 1} failed: {e}")
                    await asyncio.sleep(1 * (attempt + 1))

            if not raw_data:
                return [None] * len(symbols)

        results: list[dict | None] = []
        for sym in symbols:
            data = raw_data.get(sym)
            stock = stock_map.get(sym)
            if not data or len(data) < 30 or not stock:
                results.append(None)
                continue
            try:
                signal = evaluate_swing_signal(
                    data,
                    meta={
                        "symbol": sym,
                        "name": stock["name"],
                        "listing_days": 9999,
                        "market_cap_billion": stock.get("market_cap_billion"),
                        "industry": stock.get("industry"),
                    },
                )
            except Exception as e:
                logger.error(f"Signal evaluation failed for {sym}: {e}")
                results.append(None)
                continue

            latest = data[-1]
            close = float(latest["close"])
            stop_loss = float(signal.get("stop_loss") or close * 0.95)
            score = int(signal.get("score", 0))
            signal_type = signal.get("signal_type")
            status = (
                "green"
                if signal.get("should_buy")
                else "yellow"
                if score >= 4
                else "red"
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
                str(max(20, min(95, int(20 + ((c - r_min) / span * 75)))))
                for c in r_closes
            )
            results.append(
                {
                    "symbol": sym,
                    "name": stock["name"],
                    "price": close,
                    "stop_loss": stop_loss,
                    "r_value": float(signal.get("metrics", {}).get("r_value") or 0.0),
                    "volume_ratio": float(
                        signal.get("metrics", {}).get("volume_ratio") or 0.0
                    ),
                    "status": status,
                    "should_buy": signal.get("should_buy", False),
                    "score": score,
                    "change_pct": change,
                    "bars": bars,
                    "signal_type": signal_type,
                }
            )
        return results

    stock_map: dict[str, dict] = {s["symbol"]: s for s in all_stocks}

    for idx in range(0, total, BATCH_SIZE):
        batch = all_stocks[idx : idx + BATCH_SIZE]
        sub_batches = [
            [s["symbol"] for s in batch[i : i + SUB_BATCH_SIZE]]
            for i in range(0, len(batch), SUB_BATCH_SIZE)
        ]

        all_results = await asyncio.gather(
            *[
                _scan_sub_batch(symbols, stock_map, start_s, end_s, sem)
                for symbols in sub_batches
            ],
            return_exceptions=True,
        )

        valid: list[dict] = []
        for result in all_results:
            if isinstance(result, list):
                valid.extend([r for r in result if isinstance(r, dict)])

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
        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        rate = scanned / elapsed if elapsed > 0 else 0
        logger.info(
            f"Scanned {scanned}/{total} | green:{sum(1 for v in valid if v.get('should_buy'))} yellow:{sum(1 for v in valid if v.get('status') == 'yellow')} | {rate:.1f} stocks/s"
        )

        if idx + BATCH_SIZE < total:
            await asyncio.sleep(PAUSE_BETWEEN_BATCHES)

    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info(
        f"Full scan done in {elapsed:.0f}s ({elapsed / 60:.1f}m), {total} stocks."
    )


async def scan_loop():
    from app.core.config import settings

    delay = settings.scanner_first_delay_seconds
    logger.info(
        "Scanner loop started (local high-perf), first run in %d seconds...", delay
    )
    if delay > 0:
        await asyncio.sleep(delay)
    while True:
        try:
            await run_full_scan()
        except Exception as exc:
            logger.error(f"Scan failed: {exc}", exc_info=True)
        logger.info(f"Next scan in {SCAN_INTERVAL_HOURS} hours")
        await asyncio.sleep(SCAN_INTERVAL_HOURS * 3600)
