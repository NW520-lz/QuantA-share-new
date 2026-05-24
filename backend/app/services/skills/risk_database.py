from typing import Any

from app.services.strategy.filters import is_st_stock, is_new_stock, is_suspended


def run_risk_screening(
    data: list[dict[str, Any]], meta: dict[str, Any] | None = None
) -> dict[str, Any]:
    symbol = meta.get("symbol", "") if meta else ""
    name = meta.get("name", "") if meta else ""
    risk_flags = []
    risk_level = "low"
    risk_score = 0

    if meta:
        if is_st_stock(meta.get("name"), meta.get("tags")):
            risk_flags.append("ST_de_listed_risk")
            risk_level = "critical"
            risk_score += 10

        if is_new_stock(meta.get("listing_days")):
            risk_flags.append("new_stock_volatility")
            risk_score += 3

        if is_suspended(meta.get("is_suspended")):
            risk_flags.append("suspended")
            risk_level = "critical"
            risk_score += 10

    if data and len(data) >= 20:
        closes = [r["close"] for r in data]
        highs = [r.get("high", 0) for r in data]
        lows = [r.get("low", 0) for r in data]
        volumes = [r.get("volume", 0) for r in data]

        latest = closes[-1]
        ma20 = sum(closes[-20:]) / 20

        daily_returns = [
            (closes[i] - closes[i - 1]) / closes[i - 1]
            for i in range(1, len(closes))
            if closes[i - 1] > 0
        ]
        if daily_returns:
            import statistics

            annualized_vol = (
                statistics.stdev(daily_returns[-60:]) * (252**0.5) * 100
                if len(daily_returns) >= 60
                else statistics.stdev(daily_returns) * (252**0.5) * 100
            )
        else:
            annualized_vol = 0.0

        drawdowns = []
        peak = closes[0]
        for c in closes:
            if c > peak:
                peak = c
            if peak > 0:
                dd = (c - peak) / peak * 100
                drawdowns.append(dd)
        max_drawdown = min(drawdowns) if drawdowns else 0.0

        pct_from_ma20 = (latest - ma20) / ma20 * 100 if ma20 > 0 else 0.0

        volume_spike = False
        if len(volumes) >= 20:
            avg_vol = sum(volumes[-20:]) / 20
            volume_spike = volumes[-1] > avg_vol * 3

        if annualized_vol > 80:
            risk_flags.append(f"high_volatility:{annualized_vol:.0f}%")
            risk_score += 5
        elif annualized_vol > 50:
            risk_flags.append(f"elevated_volatility:{annualized_vol:.0f}%")
            risk_score += 2

        if max_drawdown < -30:
            risk_flags.append(f"deep_drawdown:{max_drawdown:.0f}%")
            risk_score += 4
        elif max_drawdown < -20:
            risk_flags.append(f"moderate_drawdown:{max_drawdown:.0f}%")
            risk_score += 2

        if pct_from_ma20 > 20:
            risk_flags.append("overbought_vs_ma20")
            risk_score += 3
        elif pct_from_ma20 < -20:
            risk_flags.append("oversold_vs_ma20")
            risk_score += 2

        if volume_spike:
            risk_flags.append("volume_spike_alert")
            risk_score += 2

        volatility = annualized_vol
        last_drawdown = max_drawdown
    else:
        volatility = 0.0
        last_drawdown = 0.0
        pct_from_ma20 = 0.0

    if risk_score >= 10:
        risk_level = "critical"
    elif risk_score >= 5:
        risk_level = "high"
    elif risk_score >= 2:
        risk_level = "medium"
    else:
        risk_level = "low"

    risk_detail = {
        "volatility_annual_pct": round(volatility, 1),
        "max_drawdown_pct": round(last_drawdown, 1),
        "pct_from_ma20": round(pct_from_ma20, 1),
    }

    return {
        "symbol": symbol,
        "name": name,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "risk_flags": risk_flags,
        "risk_detail": risk_detail,
        "should_avoid": risk_level == "critical",
        "position_limit_pct": 0
        if risk_level == "critical"
        else (30 if risk_level == "high" else 70 if risk_level == "medium" else 100),
    }
