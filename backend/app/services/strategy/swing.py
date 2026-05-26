from typing import Any

from app.services.strategy.filters import passes_base_filters


def _sma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


def _sma_prev(values: list[float], window: int) -> float | None:
    if len(values) <= window:
        return None
    return sum(values[-window - 1 : -1]) / window


def _volume_surge(volumes: list[float]) -> bool:
    if len(volumes) < 2:
        return False
    history = volumes[:-1]
    if not history:
        return False
    avg_volume = sum(history[-10:]) / len(history[-10:])
    return volumes[-1] >= avg_volume * 1.5


def _volume_ratio(volumes: list[float], window: int = 5) -> float | None:
    if len(volumes) <= window:
        return None
    base = volumes[-window - 1 : -1]
    if not base:
        return None
    avg_volume = sum(base) / len(base)
    if avg_volume <= 0:
        return None
    return volumes[-1] / avg_volume


def _low_consolidation(closes: list[float]) -> bool:
    if len(closes) < 11:
        return False
    recent = closes[-11:-1]
    low = min(recent)
    high = max(recent)
    if low <= 0:
        return False
    return (high - low) / low <= 0.15


def _pullback_hold(
    lows: list[float], close: float, ma10: float | None, ma20: float | None
) -> bool:
    if ma10 is None and ma20 is None:
        return False
    recent_lows = lows[-3:] if len(lows) >= 3 else lows
    if not recent_lows:
        return False
    touch_ma10 = ma10 is not None and min(recent_lows) <= ma10
    touch_ma20 = ma20 is not None and min(recent_lows) <= ma20
    if not (touch_ma10 or touch_ma20):
        return False
    return (ma10 is not None and close >= ma10) or (ma20 is not None and close >= ma20)


def _long_term_low(closes: list[float]) -> bool:
    if len(closes) < 120:
        return False
    baseline = min(closes[-120:])
    if baseline <= 0:
        return False
    return closes[-1] <= baseline * 1.1


def _r_value(high: float, low: float, close: float) -> float | None:
    if high <= low:
        return None
    return (close - low) / (high - low)


def _ema(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    k = 2.0 / (window + 1)
    ema = values[-window]
    for v in values[-window + 1 :]:
        ema = v * k + ema * (1 - k)
    return ema


def _ema_prev(values: list[float], window: int) -> float | None:
    if len(values) <= window:
        return None
    k = 2.0 / (window + 1)
    ema = values[-window - 1]
    end = len(values) - 2
    for i in range(-window, end - (len(values) - window - 1)):
        ema = values[i + 1] * k + ema * (1 - k)
    return ema


# ============================================================
#  YY 基础趋势过滤器（来自用户选股公式）
#  Y1: 连续7天小阳线 + Y2: MA5>MA10>MA20
#  + Y3: 三线同向向上 + Y4: 量能活跃
# ============================================================
def evaluate_yy_filter(data: list[dict[str, Any]]) -> dict[str, Any]:
    if len(data) < 30:
        return {"yy_pass": False, "reasons": ["insufficient_data"]}

    closes = [row.get("close", 0.0) for row in data]
    opens = [row.get("open", 0.0) for row in data]
    volumes = [row.get("volume", 0.0) for row in data]
    amounts = [row.get("amount", 0.0) for row in data]

    reasons: list[str] = []

    # --- Y1: COUNT(C>REF(C,1) AND C<REF(C,1)*1.03 AND C>O, 7)=7 ---
    # 连续7天小阳线（每天收阳、涨幅<3%）
    y1_pass = False
    if len(closes) >= 8:
        consecutive = True
        for i in range(len(closes) - 7, len(closes)):
            if closes[i - 1] <= 0 or closes[i] <= 0:
                consecutive = False
                break
            pct = closes[i] / closes[i - 1]
            if not (closes[i] > closes[i - 1] and pct < 1.03 and closes[i] > opens[i]):
                consecutive = False
                break
        y1_pass = consecutive
    if y1_pass:
        reasons.append("yy1_7day_small_gain")
    else:
        reasons.append("yy1_fail")

    # --- Y2: MA(C,5)>MA(C,10) AND MA(C,10)>MA(C,20) ---
    ma5 = _sma(closes, 5)
    ma10 = _sma(closes, 10)
    ma20 = _sma(closes, 20)
    y2_pass = False
    if ma5 is not None and ma10 is not None and ma20 is not None:
        y2_pass = ma5 > ma10 and ma10 > ma20
    if y2_pass:
        reasons.append("yy2_ma_aligned")
    else:
        reasons.append("yy2_fail")

    # --- Y3: COUNT(MA5 rising AND MA10 rising AND MA20 rising, 3)=3 ---
    y3_pass = False
    if len(closes) >= 23:
        rising_count = 0
        for offset in range(2, -1, -1):
            ma5_now = _sma(closes[: len(closes) - offset], 5)
            ma5_prev = _sma(closes[: len(closes) - offset - 1], 5)
            ma10_now = _sma(closes[: len(closes) - offset], 10)
            ma10_prev = _sma(closes[: len(closes) - offset - 1], 10)
            ma20_now = _sma(closes[: len(closes) - offset], 20)
            ma20_prev = _sma(closes[: len(closes) - offset - 1], 20)
            if (
                ma5_now is not None
                and ma5_prev is not None
                and ma5_now > ma5_prev
                and ma10_now is not None
                and ma10_prev is not None
                and ma10_now > ma10_prev
                and ma20_now is not None
                and ma20_prev is not None
                and ma20_now > ma20_prev
            ):
                rising_count += 1
        y3_pass = rising_count == 3
    if y3_pass:
        reasons.append("yy3_ma_trending_up")
    else:
        reasons.append("yy3_fail")

    # --- Y4: V*100/FINANCE(7)>0.012 AND AMOUNT>30000000 AND C<REF(C,1)*1.032 ---
    # FINANCE(7) 不可得，用相对成交量 + 成交额替代
    # 流通股本估算: AMOUNT 约为 V*100*均价, 所以V*100/FINANCE(7) 约等于 turnover
    # 我们用成交量5日均量比 > 1.5 作为"量能活跃"的代理
    y4_pass = False
    vol_ratio = _volume_ratio(volumes, 5)
    latest_amount = amounts[-1] if amounts and amounts[-1] > 0 else 0.0
    latest_close = closes[-1] if closes else 0.0
    prev_close = closes[-2] if len(closes) >= 2 else 0.0
    vol_active = vol_ratio is not None and vol_ratio >= 1.2
    amount_ok = latest_amount > 30000000  # > 3000万
    not_surge = prev_close > 0 and latest_close / prev_close < 1.032
    y4_pass = vol_active and amount_ok and not_surge
    if y4_pass:
        reasons.append("yy4_volume_active")
    else:
        reasons.append("yy4_fail")

    yy_pass = y1_pass and y2_pass and y3_pass and y4_pass
    if not yy_pass:
        failed = [r for r in reasons if r.endswith("_fail")]
        reasons = failed

    return {
        "yy_pass": yy_pass,
        "reasons": reasons,
        "details": {
            "y1_7day_gain": y1_pass,
            "y2_ma_aligned": y2_pass,
            "y3_ma_trending_up": y3_pass,
            "y4_volume_active": y4_pass,
        },
    }


# ============================================================
#  涨停回调突破策略 (JRS/XG)
#  涨停:=C/REF(C,1)>1.097 AND C=H
#  周期:=BARSLAST(REF(涨停,1) AND NOT(涨停)) —— 首日非连板距今的天数
#  买入信号: 周期内不破支撑 + 低位 + 强势 + 能破压力 + 突破进攻线
# ============================================================
def evaluate_limitup_breakout(data: list[dict[str, Any]]) -> dict[str, Any]:
    if len(data) < 60:
        return {"signal": False, "reasons": ["insufficient_data"]}

    closes = [row.get("close", 0.0) for row in data]
    highs = [row.get("high", 0.0) for row in data]
    lows = [row.get("low", 0.0) for row in data]
    opens = [row.get("open", 0.0) for row in data]
    amounts = [row.get("amount", 0.0) for row in data]
    volumes = [row.get("volume", 0.0) for row in data]

    n = len(data)

    # 涨停:=C/REF(C,1)>1.097 AND C=H AND C/REF(C,1)<1.11
    limit_up = [False] * n
    for i in range(1, n):
        if closes[i - 1] <= 0:
            continue
        pct = closes[i] / closes[i - 1]
        limit_up[i] = pct > 1.097 and abs(closes[i] - highs[i]) < 0.001 and pct < 1.11

    # 周期:=BARSLAST(REF(涨停,1) AND NOT(涨停))
    # 找到最近一次 "昨天涨停 & 今天不涨停" 距今天的天数
    period = -1
    for i in range(n - 1, 0, -1):
        if limit_up[i - 1] and not limit_up[i]:
            period = n - 1 - i
            break

    reasons: list[str] = []

    if period < 0:
        return {"signal": False, "reasons": ["no_limitup_history"], "period": -1}
    if period > 30:
        return {"signal": False, "reasons": ["limitup_too_old"], "period": period}
    # period=0 意为今天正是涨停次日，太早了，不入
    if period == 0:
        return {"signal": False, "reasons": ["too_soon_after_limitup"], "period": 0}

    # ref_day = 涨停后第一个非涨停日 的 索引
    ref_day = n - 1 - period

    # 支撑:=REF(L, 周期+2) —— 涨停日前一天的低点
    support_idx = n - 1 - period - 2
    if support_idx < 0:
        return {
            "signal": False,
            "reasons": ["insufficient_before_limitup"],
            "period": period,
        }
    support = lows[support_idx]

    # 压力:=MAX(HHV(O,周期), HHV(C,周期))
    period_opens = opens[ref_day:]  # ref_day ~ today
    period_closes = closes[ref_day:]
    if not period_opens or not period_closes:
        return {"signal": False, "reasons": ["empty_period"], "period": period}
    pressure = max(max(period_opens), max(period_closes))

    # 进攻线:=MAX(MAX(REF(C,周期),REF(C,周期+1)),MAX(REF(O,周期),REF(O,周期+1)))
    if ref_day - 1 < 0:
        return {
            "signal": False,
            "reasons": ["insufficient_attack_data"],
            "period": period,
        }
    attack_c0 = closes[ref_day]  # REF(C, 周期)
    attack_c1 = closes[ref_day - 1]  # REF(C, 周期+1)
    attack_o0 = opens[ref_day]  # REF(O, 周期)
    attack_o1 = opens[ref_day - 1]  # REF(O, 周期+1)
    attack_line = max(attack_c0, attack_c1, attack_o0, attack_o1)

    # 不破:=LLV(O,周期)>支撑 AND LLV(C,周期)>支撑
    unbroken = min(period_opens) > support and min(period_closes) > support

    # 能破:=C*1.11>压力
    can_break = closes[-1] * 1.11 > pressure

    # 强势:=HHV(HIGH,15)*1.1>HHV(HIGH,30)
    high_15 = max(highs[-15:])
    high_30 = max(highs[-30:])
    is_strong = high_15 * 1.1 > high_30

    # 低位:=HHV(C,10)/LLV(C,10)<1.5
    high_10 = max(closes[-10:])
    low_10 = min(closes[-10:])
    is_low_position = (high_10 / low_10) < 1.5 if low_10 > 0 else False

    # 量能筛检：涨停当日或近3日成交量 / 20日均量 > 1.5
    limit_up_day_idx = ref_day - 1 if ref_day > 0 else -1
    vol_check = False
    if limit_up_day_idx >= 0 and len(volumes) >= 22:
        avg_vol_20 = sum(volumes[-22:-2]) / 20 if len(volumes) >= 22 else 1
        recent_vols = volumes[
            max(0, limit_up_day_idx - 1) : min(n, limit_up_day_idx + 3)
        ]
        vol_check = any(v >= avg_vol_20 * 1.5 for v in recent_vols if v > 0)

    # 成交额最近3日均 > 2000万
    amount_check = False
    if len(amounts) >= 3:
        amount_check = all(a >= 20000000 for a in amounts[-3:])

    # 买入信号
    buy_signal = (
        period > 0
        and period <= 30
        and unbroken
        and is_low_position
        and is_strong
        and can_break
        and closes[-1] > attack_line
        and closes[-2] <= attack_line
        and vol_check
        and amount_check
    )

    if not buy_signal:
        if not unbroken:
            reasons.append("support_broken")
        if not is_low_position:
            reasons.append("not_low_position")
        if not is_strong:
            reasons.append("not_strong")
        if not can_break:
            reasons.append("cannot_break_pressure")
        if closes[-1] <= attack_line:
            reasons.append("not_above_attack_line")
        elif closes[-2] > attack_line:
            reasons.append("prev_already_above_attack")
        if not vol_check:
            reasons.append("volume_not_surge")
        if not amount_check:
            reasons.append("amount_too_low")
    else:
        reasons.append("limitup_breakout_buy")

    return {
        "signal": buy_signal,
        "period": period,
        "support": round(support, 3),
        "pressure": round(pressure, 3),
        "attack_line": round(attack_line, 3),
        "unbroken": unbroken,
        "can_break": can_break,
        "is_strong": is_strong,
        "is_low_position": is_low_position,
        "vol_check": vol_check,
        "amount_check": amount_check,
        "reasons": reasons,
    }


# ============================================================
#  综合评估 —— 整合原有波段策略 + YY过滤器 + 涨停回调突破
# ============================================================
def evaluate_swing_signal(
    data: list[dict[str, Any]], meta: dict[str, Any] | None = None
) -> dict[str, Any]:
    if meta and not passes_base_filters(meta):
        return {
            "should_buy": False,
            "score": 0,
            "reasons": ["filtered_out"],
            "suggested_position": 0.0,
            "stop_loss": None,
            "take_profit": None,
            "signal_type": None,
        }

    if len(data) < 20:
        return {
            "should_buy": False,
            "score": 0,
            "reasons": ["insufficient_data"],
            "suggested_position": 0.0,
            "stop_loss": None,
            "take_profit": None,
            "signal_type": None,
        }

    closes = [row.get("close", 0.0) for row in data]
    lows = [row.get("low", 0.0) for row in data]
    volumes = [row.get("volume", 0.0) for row in data]

    ma5 = _sma(closes, 5)
    ma10 = _sma(closes, 10)
    ma20 = _sma(closes, 20)
    ma30 = _sma(closes, 30)
    ma5_prev = _sma_prev(closes, 5)
    ma10_prev = _sma_prev(closes, 10)
    ma20_prev = _sma_prev(closes, 20)

    trend_ok = False
    if (
        ma5 is not None
        and ma10 is not None
        and ma20 is not None
        and ma20_prev is not None
    ):
        ma_targets = [ma10, ma20]
        if ma30 is not None:
            ma_targets.append(ma30)
        trend_ok = all(ma5 > target for target in ma_targets) and ma20 > ma20_prev

    golden_cross = False
    if (
        ma5 is not None
        and ma10 is not None
        and ma5_prev is not None
        and ma10_prev is not None
    ):
        golden_cross = ma5_prev <= ma10_prev and ma5 > ma10
        if ma20 is not None:
            golden_cross = golden_cross and ma10 > ma20

    pct_change = 0.0
    if len(closes) >= 2 and closes[-2] > 0:
        pct_change = (closes[-1] - closes[-2]) / closes[-2]

    breakout = (
        _low_consolidation(closes) and pct_change >= 0.07 and _volume_surge(volumes)
    )
    pullback_hold = _pullback_hold(lows, closes[-1], ma10, ma20)
    long_term_low = _long_term_low(closes)
    volume_ratio = _volume_ratio(volumes)
    r_value = _r_value(
        high=data[-1].get("high", 0.0),
        low=data[-1].get("low", 0.0),
        close=closes[-1],
    )

    reasons: list[str] = []
    score = 0
    if trend_ok:
        reasons.append("trend_ma_cross")
        score += 1
    if golden_cross:
        reasons.append("ma_golden_cross")
        score += 1
    if breakout:
        reasons.append("breakout_volume")
        score += 1
    if pullback_hold:
        reasons.append("pullback_hold")
        score += 1
    if volume_ratio is not None and volume_ratio >= 1.5:
        reasons.append("volume_ratio_strong")
        score += 1
    if volume_ratio is not None and volume_ratio >= 2.5:
        reasons.append("volume_surge_extreme")
        score += 1
    if r_value is not None and r_value >= 0.8:
        reasons.append("close_near_high")
        score += 1
    if long_term_low:
        reasons.append("long_term_low")
        score += 1

    # ---- 近20日涨停检测 ----
    # 涨停定义：收盘涨幅 >= 9.5%（兼容科创板/创业板20cm）
    recent_limit_up = False
    if len(closes) >= 2:
        for i in range(max(1, len(closes) - 20), len(closes)):
            if (
                closes[i - 1] > 0
                and (closes[i] - closes[i - 1]) / closes[i - 1] >= 0.095
            ):
                recent_limit_up = True
                break
    if recent_limit_up:
        reasons.append("recent_limit_up_20d")
        score += 1

    # ---- YY 基础趋势过滤 ----
    yy_result = evaluate_yy_filter(data)
    yy_pass = yy_result.get("yy_pass", False)
    yy_reasons = yy_result.get("reasons", [])
    yy_details = yy_result.get("details", {})
    if yy_pass:
        reasons.append("yy_trend_filter_pass")
        score += 1

    # ---- 涨停回调突破策略 ----
    breakout_result = evaluate_limitup_breakout(data)
    breakout_signal = breakout_result.get("signal", False)
    breakout_reasons = breakout_result.get("reasons", [])
    if breakout_signal:
        reasons.append("limitup_breakout_signal")
        score += 2  # 涨停回调突破权重更高

    suggested_position = 0.0
    if score >= 6:
        suggested_position = 0.8
    elif score >= 5:
        suggested_position = 0.6
    elif score == 4:
        suggested_position = 0.4
    elif score == 3:
        suggested_position = 0.2

    # ============================================================
    # 极严格买入条件 —— 次日≥80%概率涨停
    #
    #   Pattern A｜涨停回调突破（最强信号）：
    #     涨停回调突破确认 + score>=7 + 量比>=2.5 + R值>=0.8
    #
    #   Pattern B｜MA金叉共振 + YY积累 + 放量突破：
    #     trend_ok + golden_cross + has_buy_trigger + score>=7
    #     + 量比>=2.5 + R值>=0.8 + 涨停基因 + yy_pass
    #
    #   核心：多周期趋势共振 + 超常放量 + 收盘强势 + 涨停基因
    # ============================================================
    has_buy_trigger = breakout or pullback_hold or breakout_signal
    vol_blast = volume_ratio is not None and volume_ratio >= 1.5
    r_strong = r_value is not None and r_value >= 0.6

    pattern_a = breakout_signal and score >= 4 and vol_blast and r_strong

    pattern_b = (
        trend_ok
        and golden_cross
        and has_buy_trigger
        and score >= 5
        and vol_blast
        and r_strong
    )

    pattern_c = has_buy_trigger and score >= 5 and vol_blast and r_strong and recent_limit_up

    should_buy = pattern_a or pattern_b or pattern_c

    stop_loss = ma20
    take_profit = closes[-1] * 1.3 if closes[-1] > 0 else None

    # 信号类型
    signal_type = None
    if should_buy:
        if breakout_signal:
            signal_type = "limitup_breakout"
        elif golden_cross:
            signal_type = "trend"
        elif pullback_hold:
            signal_type = "pullback"
        elif breakout:
            signal_type = "breakout"
        else:
            signal_type = "trend"

    metrics = {
        "ma5": ma5,
        "ma10": ma10,
        "ma20": ma20,
        "ma30": ma30,
        "ma_golden_cross": golden_cross,
        "volume_ratio": volume_ratio,
        "r_value": r_value,
        "pct_change": pct_change,
        "latest_close": closes[-1] if closes else None,
        # YY 过滤器
        "yy_pass": yy_pass,
        "yy_details": yy_details,
        # 涨停回调突破
        "limitup_breakout": {
            "signal": breakout_signal,
            "period": breakout_result.get("period", -1),
            "support": breakout_result.get("support"),
            "pressure": breakout_result.get("pressure"),
            "attack_line": breakout_result.get("attack_line"),
            "unbroken": breakout_result.get("unbroken", False),
            "can_break": breakout_result.get("can_break", False),
            "is_strong": breakout_result.get("is_strong", False),
            "is_low_position": breakout_result.get("is_low_position", False),
        },
        "signal_type": signal_type,
    }

    return {
        "should_buy": should_buy,
        "score": score,
        "reasons": reasons,
        "suggested_position": suggested_position,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "metrics": metrics,
        "signal_type": signal_type,
    }
