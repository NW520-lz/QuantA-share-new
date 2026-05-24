from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from app.services.data.baostock import get_daily_data
from app.services.strategy.swing import evaluate_swing_signal


@dataclass
class BacktestTrade:
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    return_pct: float
    outcome: str


def _normalize_symbol(symbol: str) -> str:
    symbol = symbol.strip().lower()
    if symbol.startswith(("sh.", "sz.", "bj.")):
        return symbol
    if symbol.endswith(".sh"):
        return f"sh.{symbol[:-3]}"
    if symbol.endswith(".sz"):
        return f"sz.{symbol[:-3]}"
    return symbol


async def run_swing_backtest(
    symbol: str,
    start_date: str,
    end_date: str,
    lookback_days: int = 60,
    hold_days: int = 10,
    stop_loss_pct: float = 0.05,
    take_profit_pct: float = 0.08,
) -> dict[str, Any]:
    normalized_symbol = _normalize_symbol(symbol)
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    fetch_start = (start_dt - timedelta(days=lookback_days * 2)).strftime("%Y-%m-%d")
    data = await get_daily_data(normalized_symbol, fetch_start, end_date)
    if len(data) < lookback_days + hold_days + 2:
        return {"symbol": normalized_symbol, "trades": 0, "wins": 0, "win_rate": 0.0, "avg_return_pct": 0.0, "samples": []}

    samples: list[BacktestTrade] = []
    for idx in range(lookback_days, len(data) - hold_days - 1):
        bar = data[idx]
        if bar["date"] < start_date or bar["date"] > end_date:
            continue
        window = data[idx - lookback_days : idx + 1]
        signal = evaluate_swing_signal(window, meta={"symbol": normalized_symbol, "name": normalized_symbol, "listing_days": 9999})
        if not signal.get("should_buy"):
            continue

        entry = data[idx + 1]
        entry_price = float(entry["open"])
        tp_price = entry_price * (1 + take_profit_pct)
        sl_price = entry_price * (1 - stop_loss_pct)
        exit_price = float(data[idx + hold_days]["close"])
        exit_date = data[idx + hold_days]["date"]
        outcome = "timeout"

        for future in data[idx + 1 : idx + hold_days + 1]:
            high = float(future["high"])
            low = float(future["low"])
            if low <= sl_price:
                exit_price = sl_price
                exit_date = future["date"]
                outcome = "stop_loss"
                break
            if high >= tp_price:
                exit_price = tp_price
                exit_date = future["date"]
                outcome = "take_profit"
                break

        ret = (exit_price - entry_price) / entry_price
        samples.append(
            BacktestTrade(
                entry_date=entry["date"],
                exit_date=exit_date,
                entry_price=entry_price,
                exit_price=exit_price,
                return_pct=ret,
                outcome=outcome,
            )
        )

    wins = sum(1 for t in samples if t.return_pct > 0)
    avg_return = sum(t.return_pct for t in samples) / len(samples) if samples else 0.0
    return {
        "symbol": normalized_symbol,
        "trades": len(samples),
        "wins": wins,
        "win_rate": (wins / len(samples)) if samples else 0.0,
        "avg_return_pct": avg_return,
        "samples": [t.__dict__ for t in samples[:20]],
    }
