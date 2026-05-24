from typing import Any


def _volume_surge(volumes: list[float], multiplier: float = 1.5) -> bool:
    if len(volumes) < 2:
        return False
    history = volumes[:-1]
    if not history:
        return False
    avg = sum(history[-10:]) / len(history[-10:])
    return volumes[-1] >= avg * multiplier


def _volume_shrink(volumes: list[float]) -> bool:
    if len(volumes) < 10:
        return False
    recent = volumes[-3:]
    history = volumes[-10:-3]
    if not history:
        return False
    avg_recent = sum(recent) / len(recent)
    avg_history = sum(history) / len(history)
    return avg_recent < avg_history * 0.5


def _vwap(data: list[dict[str, Any]]) -> float | None:
    total_value = 0.0
    total_volume = 0.0
    for row in data:
        high = row.get("high", 0)
        low = row.get("low", 0)
        close = row.get("close", 0)
        vol = row.get("volume", 0)
        typical = (high + low + close) / 3
        total_value += typical * vol
        total_volume += vol
    return total_value / total_volume if total_volume > 0 else None


def run_volume_analyzer(
    data: list[dict[str, Any]], meta: dict[str, Any] | None = None
) -> dict[str, Any]:
    if len(data) < 10:
        return {
            "symbol": meta.get("symbol", "") if meta else "",
            "name": meta.get("name", "") if meta else "",
            "volume_state": "unknown",
            "volume_score": 0,
            "signals": ["insufficient_data"],
        }

    volumes = [r["volume"] for r in data]
    closes = [r["close"] for r in data]

    surge = _volume_surge(volumes)
    extreme_surge = _volume_surge(volumes, 2.5)
    shrink = _volume_shrink(volumes)

    vol5_avg = sum(volumes[-5:]) / len(volumes[-5:])
    vol20_avg = (
        sum(volumes[-20:]) / len(volumes[-20:]) if len(volumes) >= 20 else vol5_avg
    )
    vol50_avg = (
        sum(volumes[-50:]) / len(volumes[-50:]) if len(volumes) >= 50 else vol20_avg
    )

    latest_vol = volumes[-1]
    vol_ratio_5 = latest_vol / vol5_avg if vol5_avg > 0 else 1.0
    vol_ratio_20 = latest_vol / vol20_avg if vol20_avg > 0 else 1.0
    vol_ratio_50 = latest_vol / vol50_avg if vol50_avg > 0 else 1.0

    vwap_val = _vwap(data[-20:])
    latest_close = closes[-1]
    vs_vwap = ((latest_close - vwap_val) / vwap_val * 100) if vwap_val else None

    signals = []
    score = 0

    if extreme_surge:
        signals.append("extreme_surge")
        score += 1
    elif surge:
        signals.append("volume_surge")
        score += 3

    if shrink:
        signals.append("volume_shrink_to_low")
        score += 1

    if vol_ratio_5 >= 2.0:
        signals.append("volume_double_5d")
    if vol_ratio_20 >= 2.0:
        signals.append("volume_double_20d")
        score += 1
    if vol_ratio_20 >= 1.2:
        signals.append("volume_active")
        score += 1
    elif vol_ratio_20 >= 0.8:
        signals.append("volume_normal")
    else:
        signals.append("volume_thin")

    if vs_vwap is not None:
        if vs_vwap > 2:
            signals.append("above_vwap")
            score += 1
        elif vs_vwap < -2:
            signals.append("below_vwap")

    price_up = closes[-1] > closes[-2] if len(closes) >= 2 else False
    if surge and price_up:
        signals.append("volume_price_confirmation")
        score += 2
    elif surge and not price_up:
        signals.append("volume_divergence")

    if vol_ratio_20 >= 1.5 and score >= 4:
        state = "strong_active"
    elif score >= 3:
        state = "active"
    elif score >= 1:
        state = "normal"
    elif shrink:
        state = "dormant"
    else:
        state = "thin"

    return {
        "symbol": meta.get("symbol", "") if meta else "",
        "name": meta.get("name", "") if meta else "",
        "volume_state": state,
        "volume_score": score,
        "signals": signals,
        "vol_ratio_5": round(vol_ratio_5, 2),
        "vol_ratio_20": round(vol_ratio_20, 2),
        "vol_ratio_50": round(vol_ratio_50, 2),
        "vol5_avg": int(vol5_avg),
        "vol20_avg": int(vol20_avg),
        "latest_volume": int(latest_vol),
        "vwap": round(vwap_val, 2) if vwap_val else None,
        "vs_vwap_pct": round(vs_vwap, 2) if vs_vwap else None,
        "is_surge": surge,
        "is_shrink": shrink,
    }
