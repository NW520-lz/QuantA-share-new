from typing import Any

from app.services.data.baostock import get_daily_data
from app.services.strategy.backtest import run_swing_backtest


async def run_backtest_skill(
    symbol: str,
    start_date: str = "2024-01-01",
    end_date: str = "2026-05-20",
    lookback_days: int = 60,
    hold_days: int = 10,
    stop_loss_pct: float = 0.05,
    take_profit_pct: float = 0.08,
) -> dict[str, Any]:
    result = await run_swing_backtest(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        lookback_days=lookback_days,
        hold_days=hold_days,
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
    )

    win_rate = result.get("win_rate", 0) * 100
    report = _generate_report(symbol, result, win_rate, start_date, end_date)

    return {
        "symbol": symbol,
        "start_date": start_date,
        "end_date": end_date,
        "total_trades": result.get("trades", 0),
        "wins": result.get("wins", 0),
        "losses": result.get("trades", 0) - result.get("wins", 0),
        "win_rate_pct": round(win_rate, 1),
        "avg_return_pct": round(result.get("avg_return_pct", 0) * 100, 2),
        "strategy_params": {
            "lookback_days": lookback_days,
            "hold_days": hold_days,
            "stop_loss_pct": stop_loss_pct * 100,
            "take_profit_pct": take_profit_pct * 100,
        },
        "summary_report": report,
        "recent_trades": result.get("samples", [])[-10:],
    }


def _generate_report(
    symbol: str, result: dict, win_rate: float, start_date: str, end_date: str
) -> str:
    trades = result.get("trades", 0)
    wins = result.get("wins", 0)
    avg_ret = result.get("avg_return_pct", 0) * 100

    if trades == 0:
        return f"标的 {symbol} 在 {start_date} 至 {end_date} 期间无符合条件的交易信号。"

    grade = (
        "优秀"
        if win_rate >= 55 and avg_ret > 2
        else "良好"
        if win_rate >= 50
        else "一般"
        if win_rate >= 40
        else "较差"
    )

    outcomes: dict[str, int] = {}
    for t in result.get("samples", []):
        outcomes[t.get("outcome", "unknown")] = (
            outcomes.get(t.get("outcome", "unknown"), 0) + 1
        )

    stop_loss_count = outcomes.get("stop_loss", 0)
    take_profit_count = outcomes.get("take_profit", 0)
    timeout_count = outcomes.get("timeout", 0)

    report = (
        f"=== {symbol} 回测报告 ===\n"
        f"回测区间: {start_date} ~ {end_date}\n"
        f"总交易次数: {trades} | 盈利: {wins} | 亏损: {trades - wins}\n"
        f"胜率: {win_rate:.1f}% | 平均收益: {avg_ret:+.2f}%\n"
        f"策略评级: {grade}\n"
        f"出场分布: 止盈={take_profit_count} 止损={stop_loss_count} 超时={timeout_count}\n"
    )

    if win_rate >= 50:
        report += "\n结论: 策略在该标的上表现良好，建议纳入候选池。"
    elif win_rate >= 40:
        report += "\n结论: 策略有效性边际，建议结合其他因子优化参数。"
    else:
        report += "\n结论: 当前策略不适用于该标的，建议更换标的或调整参数。"

    return report
