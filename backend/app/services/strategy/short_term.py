from typing import Any

from app.services.strategy.filters import passes_base_filters


def _sentiment_score(
    promotion_rate: float,
    limit_up_count: int,
    limit_down_count: int,
    breadth_pct: float,
    leading_stock_negative_feedback: bool,
) -> tuple[float, str, list[str]]:
    score = max(0.0, min(100.0, promotion_rate * 100.0))
    score += (breadth_pct - 0.5) * 60.0

    if limit_up_count + limit_down_count > 0:
        imbalance = (limit_up_count - limit_down_count) / (limit_up_count + limit_down_count)
        score += imbalance * 20.0

    if leading_stock_negative_feedback:
        score -= 30.0

    score = max(0.0, min(100.0, score))
    if score >= 70:
        label = "强势"
    elif score >= 55:
        label = "偏强"
    elif score >= 35:
        label = "中性"
    elif score >= 20:
        label = "偏弱"
    else:
        label = "退潮"

    risk_flags: list[str] = []
    if score < 35:
        risk_flags.append("sentiment_weak")
    if leading_stock_negative_feedback:
        risk_flags.append("leading_negative_feedback")

    return score, label, risk_flags


def evaluate_short_term_signal(context: dict[str, Any], meta: dict[str, Any] | None = None) -> dict[str, Any]:
    if meta and not passes_base_filters(meta):
        return {
            "should_buy": False,
            "score": 0,
            "reasons": ["filtered_out"],
            "suggested_position": 0.0,
            "stop_loss_pct": 0.05,
            "take_profit_min_pct": 0.03,
            "take_profit_max_pct": 0.08,
            "risk_flags": [],
        }

    promotion_rate = float(context.get("promotion_rate", 0.0))
    expected_open_pct = float(context.get("expected_open_pct", 0.0))
    actual_open_pct = float(context.get("actual_open_pct", 0.0))
    limit_up_count = int(context.get("limit_up_count", 0))
    limit_down_count = int(context.get("limit_down_count", 0))
    breadth_pct = float(context.get("breadth_pct", 0.0))
    if promotion_rate > 1:
        promotion_rate = promotion_rate / 100.0
    if breadth_pct > 1:
        breadth_pct = breadth_pct / 100.0
    leading_stock_negative_feedback = bool(context.get("leading_stock_negative_feedback", False))
    intraday_rebound = bool(context.get("intraday_rebound", False))
    board_lock = bool(context.get("board_lock", False))
    theme_mainline = bool(context.get("theme_mainline", True))
    turnover_rate = context.get("turnover_rate")

    sentiment_score, sentiment_label, sentiment_flags = _sentiment_score(
        promotion_rate=promotion_rate,
        limit_up_count=limit_up_count,
        limit_down_count=limit_down_count,
        breadth_pct=breadth_pct,
        leading_stock_negative_feedback=leading_stock_negative_feedback,
    )

    reasons: list[str] = []
    risk_flags: list[str] = []
    score = 0

    sentiment_ok = promotion_rate > 0.3 and not leading_stock_negative_feedback
    if sentiment_ok:
        reasons.append("sentiment_strong")
        score += 1
    elif promotion_rate < 0.1:
        risk_flags.append("sentiment_cooling")

    weak_to_strong = expected_open_pct <= -2.0 and actual_open_pct >= 0.0
    if weak_to_strong:
        reasons.append("weak_to_strong")
        score += 1

    if intraday_rebound:
        reasons.append("intraday_rebound")
        score += 1

    if board_lock:
        reasons.append("board_lock")
        score += 1

    if theme_mainline:
        reasons.append("theme_mainline")
        score += 1
    else:
        risk_flags.append("non_mainline_theme")

    if leading_stock_negative_feedback:
        risk_flags.append("leading_negative_feedback")
        score = 0

    if turnover_rate is not None:
        try:
            turnover_value = float(turnover_rate)
            if turnover_value > 0.4:
                risk_flags.append("high_turnover")
        except ValueError:
            pass

    suggested_position = 0.0
    if score >= 4:
        suggested_position = 1.0
    elif score == 3:
        suggested_position = 0.6
    elif score == 2:
        suggested_position = 0.3

    should_buy = score >= 3 and not leading_stock_negative_feedback

    risk_flags.extend(sentiment_flags)

    return {
        "should_buy": should_buy,
        "score": score,
        "reasons": reasons,
        "suggested_position": suggested_position,
        "stop_loss_pct": 0.05,
        "take_profit_min_pct": 0.03,
        "take_profit_max_pct": 0.08,
        "risk_flags": risk_flags,
        "sentiment_score": sentiment_score,
        "sentiment_label": sentiment_label,
    }


def evaluate_market_sentiment(payload: dict[str, Any]) -> dict[str, Any]:
    promotion_rate = float(payload.get("promotion_rate", 0.0))
    breadth_pct = float(payload.get("breadth_pct", 0.0))
    if promotion_rate > 1:
        promotion_rate = promotion_rate / 100.0
    if breadth_pct > 1:
        breadth_pct = breadth_pct / 100.0

    sentiment_score, label, risk_flags = _sentiment_score(
        promotion_rate=promotion_rate,
        limit_up_count=int(payload.get("limit_up_count", 0)),
        limit_down_count=int(payload.get("limit_down_count", 0)),
        breadth_pct=breadth_pct,
        leading_stock_negative_feedback=bool(payload.get("leading_stock_negative_feedback", False)),
    )

    return {
        "sentiment_score": sentiment_score,
        "label": label,
        "risk_flags": risk_flags,
    }
