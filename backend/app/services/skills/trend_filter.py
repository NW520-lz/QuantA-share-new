from typing import Any

from app.services.strategy.filters import passes_base_filters


def _sma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


def _slope(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    subset = values[-window:]
    n = len(subset)
    x_mean = (n - 1) / 2
    y_mean = sum(subset) / n
    numerator = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(subset))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    if denominator == 0:
        return None
    base = subset[-n // 2] if n > 1 and subset[-n // 2] > 0 else y_mean
    return (numerator / denominator) / base if base > 0 else 0.0


def run_trend_filter(
    data: list[dict[str, Any]], meta: dict[str, Any] | None = None
) -> dict[str, Any]:
    if meta and not passes_base_filters(meta):
        return {
            "symbol": meta.get("symbol", ""),
            "name": meta.get("name", ""),
            "trend_direction": "unknown",
            "trend_strength_pct": 0,
            "score": 0,
            "signals": ["filtered_out"],
            "ma5": None,
            "ma10": None,
            "ma20": None,
            "ma60": None,
            "ma120": None,
            "ma_state": "unknown",
            "volume_trend": "unknown",
            "latest_close": None,
        }

    if len(data) < 20:
        return {
            "symbol": meta.get("symbol", ""),
            "name": meta.get("name", ""),
            "trend_direction": "unknown",
            "trend_strength_pct": 0,
            "score": 0,
            "signals": ["insufficient_data"],
            "ma5": None,
            "ma10": None,
            "ma20": None,
            "ma60": None,
            "ma120": None,
            "ma_state": "unknown",
            "volume_trend": "unknown",
            "latest_close": None,
        }

    closes = [r["close"] for r in data]
    volumes = [r["volume"] for r in data]

    ma5 = _sma(closes, 5)
    ma10 = _sma(closes, 10)
    ma20 = _sma(closes, 20)
    ma60 = _sma(closes, 60)
    ma120 = _sma(closes, 120)

    sma5_slope = _slope(closes, 5)
    sma20_slope = _slope(closes, 20)
    vol5_avg = sum(volumes[-5:]) / len(volumes[-5:]) if volumes else 0
    vol20_avg = (
        sum(volumes[-20:]) / len(volumes[-20:]) if len(volumes) >= 20 else vol5_avg
    )
    vol_trend = (
        "increase"
        if vol5_avg > vol20_avg * 1.1
        else "decrease"
        if vol5_avg < vol20_avg * 0.9
        else "stable"
    )

    signals = []
    score = 0

    if all(v is not None for v in [ma5, ma10, ma20]):
        if ma5 > ma10 > ma20:  # type: ignore[operator]
            signals.append("bullish_alignment")
            score += 3
        elif ma5 < ma10 < ma20:  # type: ignore[operator]
            signals.append("bearish_alignment")
            score -= 1

    if sma20_slope is not None:
        if sma20_slope > 0.002:
            signals.append("ma20_uptrend")
            score += 2
        elif sma20_slope < -0.002:
            signals.append("ma20_downtrend")
            score -= 2

    if sma5_slope is not None and sma20_slope is not None:
        if sma5_slope > sma20_slope > 0:
            signals.append("acceleration")
            score += 1

    if ma60 is not None and ma20 is not None and ma20 > ma60:  # type: ignore[operator]
        signals.append("medium_trend_bull")
        score += 1

    if ma120 is not None and closes[-1] > ma120:
        signals.append("above_ma120")
        score += 1
    elif ma120 is not None:
        signals.append("below_ma120")

    latest = closes[-1] if closes else None
    if latest and ma20:
        pct_from_ma20 = (latest - ma20) / ma20 * 100
        signals.append(f"price_vs_ma20:{pct_from_ma20:+.1f}%")

    if score >= 4:
        direction = "strong_bull"
        strength = min(100, 50 + score * 8)
    elif score >= 2:
        direction = "bull"
        strength = 50 + score * 5
    elif score >= 0:
        direction = "neutral"
        strength = 40 + score * 5
    elif score >= -2:
        direction = "bear"
        strength = 30 + abs(score) * 3
    else:
        direction = "strong_bear"
        strength = max(5, 20 - abs(score) * 5)

    if ma5 and ma10 and ma20:
        if ma5 > ma10 > ma20:  # type: ignore[operator]
            ma_state = "long_arranged"
        elif ma5 < ma10 < ma20:  # type: ignore[operator]
            ma_state = "short_arranged"
        elif ma5 > ma10 and ma10 < ma20:  # type: ignore[operator]
            ma_state = "golden_crossing"
        elif ma5 < ma10 and ma10 > ma20:  # type: ignore[operator]
            ma_state = "death_crossing"
        else:
            ma_state = "tangled"
    else:
        ma_state = "unknown"

    return {
        "symbol": meta.get("symbol", "") if meta else "",
        "name": meta.get("name", "") if meta else "",
        "trend_direction": direction,
        "trend_strength_pct": strength,
        "score": score,
        "signals": signals,
        "ma5": round(ma5, 2) if ma5 else None,
        "ma10": round(ma10, 2) if ma10 else None,
        "ma20": round(ma20, 2) if ma20 else None,
        "ma60": round(ma60, 2) if ma60 else None,
        "ma120": round(ma120, 2) if ma120 else None,
        "ma_state": ma_state,
        "volume_trend": vol_trend,
        "latest_close": round(latest, 2) if latest else None,
    }
