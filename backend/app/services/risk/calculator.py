from typing import Any


def calculate_risk(payload: dict[str, Any]) -> dict[str, Any]:
    equity = float(payload.get("account_equity", 0.0))
    price = float(payload.get("price", 0.0))
    max_risk_pct = float(payload.get("max_risk_pct", 0.02))
    stop_loss_pct = float(payload.get("stop_loss_pct", 0.05))
    take_profit_pct = float(payload.get("take_profit_pct", 0.3))
    max_position_pct = float(payload.get("max_position_pct", 0.7))

    if equity <= 0 or price <= 0 or stop_loss_pct <= 0:
        return {
            "max_shares": 0.0,
            "max_position_value": 0.0,
            "stop_loss_price": None,
            "take_profit_price": None,
            "risk_pct_used": 0.0,
            "beta": payload.get("beta"),
        }

    risk_amount = equity * max_risk_pct
    raw_max_shares = risk_amount / (price * stop_loss_pct)
    raw_position_value = raw_max_shares * price

    cap_value = equity * max_position_pct
    if raw_position_value > cap_value:
        max_position_value = cap_value
        max_shares = cap_value / price
        risk_pct_used = (max_shares * price * stop_loss_pct) / equity
    else:
        max_position_value = raw_position_value
        max_shares = raw_max_shares
        risk_pct_used = max_risk_pct

    stop_loss_price = price * (1 - stop_loss_pct)
    take_profit_price = price * (1 + take_profit_pct)

    return {
        "max_shares": max_shares,
        "max_position_value": max_position_value,
        "stop_loss_price": stop_loss_price,
        "take_profit_price": take_profit_price,
        "risk_pct_used": risk_pct_used,
        "beta": payload.get("beta"),
    }
