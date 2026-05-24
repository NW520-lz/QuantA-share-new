from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone, timedelta

from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.models.scan_result import ScanResult
from app.services.data.baostock import get_all_a_stocks, get_daily_data
from app.services.skills.backtest_runner import run_backtest_skill
from app.services.skills.risk_database import run_risk_screening
from app.services.skills.trend_filter import run_trend_filter
from app.services.skills.volume_analyzer import run_volume_analyzer
from app.services.strategy.swing import evaluate_swing_signal
from app.services.ai.web_search import web_search


def _normalize_symbol(symbol: str) -> str:
    s = (symbol or "").strip().lower()
    if not s:
        return "sh.600519"
    if s.startswith(("sh.", "sz.", "bj.")):
        return s
    if s.endswith((".sh", ".sz", ".bj")):
        code, market = s.split(".", 1)
        return f"{market}.{code}"
    if s.isdigit():
        if s.startswith("6"):
            return f"sh.{s}"
        if s.startswith(("0", "2", "3")):
            return f"sz.{s}"
        if s.startswith(("4", "8")):
            return f"bj.{s}"
    return s


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_stocks",
            "description": "搜索A股标的，通过代码或名称模糊匹配。返回匹配的股票列表（代码、名称）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "股票代码或名称关键词，如 600519 或 茅台",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_data",
            "description": "获取指定股票的日线OHLCV数据。返回日期、开盘、最高、最低、收盘、成交量。",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "股票代码，格式 sh.600519 或 sz.000858",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "起始日期 YYYY-MM-DD",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "结束日期 YYYY-MM-DD",
                    },
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_trend",
            "description": "趋势过滤分析：多周期均线排列、趋势方向、强度评分。返回trend_direction(strong_bull/bull/neutral/bear/strong_bear)、score、ma_state。",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "股票代码 sh.600519"}
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_volume",
            "description": "量能分析：放量/缩量检测、量价比率、VWAP偏离。返回volume_state、volume_score、vol_ratio_20、is_surge。",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "股票代码 sh.600519"}
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "assess_risk",
            "description": "风险筛查：波动率、最大回撤、ST风险、仓位限制。返回risk_level(critical/high/medium/low)、risk_score、position_limit_pct。",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "股票代码 sh.600519"}
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_backtest",
            "description": "运行swing策略历史回测。返回胜率、收益率、总交易次数、策略评级。",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "股票代码 sh.600519"},
                    "start_date": {
                        "type": "string",
                        "description": "起始日期 YYYY-MM-DD，默认 2024-01-01",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "结束日期 YYYY-MM-DD，默认今天",
                    },
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "full_analysis",
            "description": "全维度分析：一次返回指定股票的趋势+量能+风险+回测的综合报告。",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "股票代码 sh.600519"}
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_scan_status",
            "description": "获取全A市场扫描状态：已扫描多少只股票、上次扫描时间。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_candidates",
            "description": "获取当前市场Top候选股票：买点信号(green)和观察信号(yellow)的排行榜，含价格、R值、量比。",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "返回数量，默认10"}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_sentiment",
            "description": "获取当前全A市场情绪指标：看多/看空/退潮，信心指数，buy信号占比。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "explain_strategy",
            "description": "解释QuantA-Share的策略体系：波段策略和短线策略的完整规则、开仓条件、仓位标准、止盈止损。",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "description": "swing(波段)或short(短线)或all(全部)",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_info",
            "description": "获取QuantA-Share系统信息：版本、页面功能、可用的分析工具列表。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "联网搜索最新信息、新闻、资讯。用于获取AI训练数据之外的最新消息，如最新政策、行业动态、个股新闻、市场热点。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，如 '稀土最新政策2026' 或 '茅台最新公告'",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "返回结果数，默认5",
                    },
                },
                "required": ["query"],
            },
        },
    },
]

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
DEFAULT_START = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%d")

STRATEGY_RULES = """=== QuantA-Share 策略体系 ===

【波段策略】主升浪趋势模式
- 开仓: 5日线上穿所有均线+20日线拐头向上，低位横盘后放量阳线≥7%，或回踩10/20日线止跌
- 仓位: 启动3-5成→趋势确认5-7成→主升浪≤7成
- 止盈: 涨幅30%分批减仓，或出现长上影线/量价背离
- 止损: 跌破20日线且3日内未收回清仓，5日线拐头+缩量清仓
- 过滤: 回避ST/退市/上市<60天，选周线月线历史低位的熟悉标的
- 持仓: 5-15天

【短线策略】情绪分歧模式
- 开仓: 赚钱效应强(连板晋级>30%)，竞价弱转强(-2%→平开)，板上确认封单坚决
- 仓位: 确定性30-60%→2-3成，70-80%→3-5成，90%+→满仓
- 止盈: 3-8%分批止盈，高位放量滞涨/炸板立即离场
- 止损: 亏损5%无条件清仓，竞价弱于预期/盘中放量下杀
- 过滤: 不做高低切/补涨龙/首板，回避退潮期(晋级<10%)
- 持仓: 1-3天"""

SYSTEM_INFO = """=== QuantA-Share 系统信息 ===
版本: Institutional V2.4
数据源: BaoStock (主) + akshare (备)
AI模型: DeepSeek (deepseek-v4-pro)

页面功能:
- 选股看板: 全A实时扫描，swing信号评估，市场情绪仪表盘
- 策略参数: 波段/短线双模式参数配置
- 复盘日志: 批量回测+全A扫描，落库+历史记录
- 持仓风控: 仓位列表+风险计算器
- AI对话: 多工具AI(趋势/量能/风险/回测/搜索)

可用分析维度:
- 趋势过滤: MA5/10/20/60/120排列+斜率评分
- 量能分析: 量比/VWAP/放量缩量检测
- 风险筛查: 年化波动率/最大回撤/ST过滤/仓位限制
- 策略回测: 滑动窗口swing回测+胜率/收益统计"""


def _display_stock_list(stocks: list[dict], max_show: int = 10) -> str:
    if not stocks:
        return "未找到匹配的股票。"
    result = [f"找到 {len(stocks)} 只股票，前 {min(max_show, len(stocks))} 只："]
    for s in stocks[:max_show]:
        result.append(f"  {s['symbol']}  {s['name']}")
    if len(stocks) > max_show:
        result.append(f"  ... 还有 {len(stocks) - max_show} 只")
    return "\n".join(result)


async def execute_tool(name: str, args: dict[str, Any]) -> str:
    symbol = _normalize_symbol(args.get("symbol", "sh.600519"))
    start = args.get("start_date") or DEFAULT_START
    end = args.get("end_date") or TODAY

    if name == "search_stocks":
        query = args.get("query", "").strip().lower()
        all_stocks = await get_all_a_stocks()
        matched = [
            s for s in all_stocks if query in s["code"] or query in s["name"].lower()
        ]
        return _display_stock_list(matched)

    if name == "get_stock_data":
        data = await get_daily_data(symbol, start, end)
        if not data:
            return f"标的 {symbol} 在 {start} ~ {end} 期间无数据。"
        summary = f"{symbol} 日线数据 ({start} ~ {end})，共 {len(data)} 条：\n"
        for r in data[-5:]:
            summary += f"  {r['date']} O:{r['open']:.2f} H:{r['high']:.2f} L:{r['low']:.2f} C:{r['close']:.2f} V:{r['volume']:.0f}\n"
        return summary

    if name == "analyze_trend":
        data = await get_daily_data(symbol, DEFAULT_START, TODAY)
        if not data:
            return f"无法获取 {symbol} 的数据。"
        result = run_trend_filter(data, {"symbol": symbol, "name": ""})
        return json.dumps(
            {
                "symbol": symbol,
                "trend_direction": result["trend_direction"],
                "trend_strength_pct": result["trend_strength_pct"],
                "ma_state": result["ma_state"],
                "score": result["score"],
                "ma5": result["ma5"],
                "ma10": result["ma10"],
                "ma20": result["ma20"],
                "signals": result["signals"],
                "latest_close": result["latest_close"],
            },
            ensure_ascii=False,
            indent=2,
        )

    if name == "analyze_volume":
        data = await get_daily_data(symbol, DEFAULT_START, TODAY)
        if not data:
            return f"无法获取 {symbol} 的数据。"
        result = run_volume_analyzer(data, {"symbol": symbol, "name": ""})
        return json.dumps(
            {
                "symbol": symbol,
                "volume_state": result["volume_state"],
                "volume_score": result["volume_score"],
                "vol_ratio_5": result["vol_ratio_5"],
                "vol_ratio_20": result["vol_ratio_20"],
                "vwap": result["vwap"],
                "vs_vwap_pct": result["vs_vwap_pct"],
                "is_surge": result["is_surge"],
                "is_shrink": result["is_shrink"],
                "signals": result["signals"],
            },
            ensure_ascii=False,
            indent=2,
        )

    if name == "assess_risk":
        data = await get_daily_data(symbol, DEFAULT_START, TODAY)
        if not data:
            return f"无法获取 {symbol} 的数据。"
        result = run_risk_screening(data, {"symbol": symbol, "name": ""})
        return json.dumps(
            {
                "symbol": symbol,
                "risk_level": result["risk_level"],
                "risk_score": result["risk_score"],
                "should_avoid": result["should_avoid"],
                "position_limit_pct": result["position_limit_pct"],
                "risk_flags": result["risk_flags"],
                "risk_detail": {k: v for k, v in result.get("risk_detail", {}).items()},
            },
            ensure_ascii=False,
            indent=2,
        )

    if name == "run_backtest":
        result = await run_backtest_skill(symbol=symbol, start_date=start, end_date=end)
        return json.dumps(
            {
                "symbol": symbol,
                "start_date": start,
                "end_date": end,
                "total_trades": result["total_trades"],
                "win_rate_pct": result["win_rate_pct"],
                "avg_return_pct": result["avg_return_pct"],
                "summary_report": result["summary_report"],
            },
            ensure_ascii=False,
            indent=2,
        )

    if name == "full_analysis":
        data = await get_daily_data(symbol, DEFAULT_START, TODAY)
        if not data:
            return f"无法获取 {symbol} 的数据。"
        trend = run_trend_filter(data, {"symbol": symbol, "name": ""})
        volume = run_volume_analyzer(data, {"symbol": symbol, "name": ""})
        risk = run_risk_screening(data, {"symbol": symbol, "name": ""})
        bt = await run_backtest_skill(
            symbol=symbol, start_date="2024-01-01", end_date=TODAY
        )

        return json.dumps(
            {
                "symbol": symbol,
                "analysis_time": TODAY,
                "data_rows": len(data),
                "latest_price": trend.get("latest_close"),
                "trend": {
                    "direction": trend.get("trend_direction"),
                    "score": trend.get("score"),
                    "ma_state": trend.get("ma_state"),
                },
                "volume": {
                    "state": volume.get("volume_state"),
                    "score": volume.get("volume_score"),
                    "vol_ratio_20": volume.get("vol_ratio_20"),
                },
                "risk": {
                    "level": risk.get("risk_level"),
                    "score": risk.get("risk_score"),
                    "position_limit": risk.get("position_limit_pct"),
                },
                "backtest": {
                    "trades": bt.get("total_trades"),
                    "win_rate": bt.get("win_rate_pct"),
                    "avg_return": bt.get("avg_return_pct"),
                },
            },
            ensure_ascii=False,
            indent=2,
        )

    if name == "get_scan_status":
        async with AsyncSessionLocal() as db:
            count = await db.scalar(
                select(func.count()).select_from(select(ScanResult).subquery())
            )
            latest = await db.execute(
                select(ScanResult.scanned_at)
                .order_by(ScanResult.scanned_at.desc())
                .limit(1)
            )
            latest_time = latest.scalar()
        return json.dumps(
            {
                "total_scanned": count or 0,
                "last_scan_at": latest_time.isoformat() if latest_time else "尚未完成",
                "scan_interval": "每4小时自动扫描",
                "note": "全A股4358只标的，分批扫描中"
                if not latest_time
                else f"已扫描{count}只，下次4小时后更新",
            },
            ensure_ascii=False,
        )

    if name == "get_top_candidates":
        limit = int(args.get("limit", 10))
        async with AsyncSessionLocal() as db:
            greens = await db.execute(
                select(ScanResult)
                .where(ScanResult.should_buy == True)
                .order_by(ScanResult.score.desc())
                .limit(limit)
            )
            green_rows = greens.scalars().all()
            yellows = await db.execute(
                select(ScanResult)
                .where(ScanResult.status == "yellow")
                .order_by(ScanResult.score.desc())
                .limit(max(0, limit - len(green_rows)))
            )
            yellow_rows = yellows.scalars().all()

        result = []
        if green_rows:
            result.append(f"🟢 Buy信号 ({len(green_rows)}只):")
            for r in green_rows:
                result.append(
                    f"  {r.symbol} {r.name} 价格{r.price:.2f} R={r.r_value:.2f} 量比={r.volume_ratio:.2f}"
                )
        if yellow_rows:
            result.append(f"🟡 观察信号 ({len(yellow_rows)}只):")
            for r in yellow_rows:
                result.append(
                    f"  {r.symbol} {r.name} 价格{r.price:.2f} R={r.r_value:.2f} 量比={r.volume_ratio:.2f}"
                )
        if not result:
            result.append("暂无扫描结果，后台正在首次扫描中。")
        return "\n".join(result)

    if name == "get_market_sentiment":
        async with AsyncSessionLocal() as db:
            total = await db.scalar(
                select(func.count()).select_from(select(ScanResult).subquery())
            )
            buy_count = await db.scalar(
                select(func.count()).where(ScanResult.should_buy == True)
            )
        promotion_rate = (buy_count / total * 100) if total else 0
        if promotion_rate >= 30:
            label, score = "看多", min(90, 50 + promotion_rate)
        elif promotion_rate >= 15:
            label, score = "震荡", 40 + promotion_rate
        else:
            label, score = "退潮", max(10, promotion_rate)
        return json.dumps(
            {
                "sentiment_label": label,
                "sentiment_score": round(score, 1),
                "total_scanned": total or 0,
                "buy_count": buy_count or 0,
                "buy_ratio_pct": round(promotion_rate, 1),
            },
            ensure_ascii=False,
        )

    if name == "explain_strategy":
        mode = args.get("mode", "all")
        if mode == "swing":
            return STRATEGY_RULES.split("【短线策略】")[0].strip()
        elif mode == "short":
            return "【短线策略】" + STRATEGY_RULES.split("【短线策略】")[1].strip()
        return STRATEGY_RULES

    if name == "get_system_info":
        return SYSTEM_INFO

    if name == "web_search":
        query = args.get("query", "")
        max_results = int(args.get("max_results", 5))
        if not query:
            return "请提供搜索关键词"
        return await web_search(query, max_results)

    return f"未知工具: {name}"
