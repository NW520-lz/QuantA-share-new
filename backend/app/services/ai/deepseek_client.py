from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.schemas.ai import ChatRequest
from app.services.ai.tools import TOOL_DEFINITIONS, execute_tool

logger = logging.getLogger("ai")

SYSTEM_PROMPT = """你是QuantA-Share的量化AI助手，拥有实时A股数据分析和策略回测能力。

你可以使用以下工具获取实时数据：

【股票分析】
- search_stocks: 搜索A股标的，通过代码/名称模糊匹配
- get_stock_data: 获取日线OHLCV K线数据
- full_analysis: 全维度分析(趋势+量能+风险+回测四合一)
- analyze_trend: 仅趋势分析（MA排列/方向/评分）
- analyze_volume: 仅量能分析（放量/缩量/VWAP）
- assess_risk: 仅风险筛查（波动率/回撤/仓位限制）
- run_backtest: 仅策略回测（胜率/收益率/交易数）

【市场全局】
- get_scan_status: 全A扫描进度（已扫多少只/上次扫描时间）
- get_top_candidates: Top买入/观察候选排行
- get_market_sentiment: 当前市场情绪（看多/震荡/退潮+信心指数）

【系统知识】
- explain_strategy: 解释波段/短线策略规则
- get_system_info: 系统功能和架构介绍

【联网搜索】
- web_search: 搜索最新资讯、政策、行业动态、个股新闻（Tavily+Brave双引擎）

重要规则：
1. 用户提到具体股票时，必须先调用工具获取真实数据再回答，绝不凭空编造。
2. 用户问"现在什么股票好"时，调用get_top_candidates + get_market_sentiment。
3. 用户问系统功能/策略时，调用explain_strategy或get_system_info。
4. 用中文回答，结构清晰，先结论后数据，使用###标题、**加粗**、列表等markdown格式。
5. 如果数据不可用，如实告知并给出建议。
6. 分析风格：量化、结构化、风险优先。关注RSI超买超卖、MACD金叉死叉、均线排列、量价配合等量化指标。"""


async def _call_api(messages: list[dict], tools: list[dict] | None = None) -> dict:
    url = f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "model": settings.deepseek_model,
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
        "max_tokens": 4096,
        "messages": messages,
        "stream": False,
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"

    timeout = httpx.Timeout(timeout=settings.deepseek_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, headers=headers, json=body)
        response.raise_for_status()
        return response.json()


def _extract_text(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        return ""
    message = (choices[0] or {}).get("message") or {}
    content = message.get("content")
    if isinstance(content, str) and content:
        return content
    reasoning = message.get("reasoning_content")
    if isinstance(reasoning, str) and reasoning:
        return reasoning
    return ""


async def chat_deepseek(payload: ChatRequest) -> str:
    if not settings.deepseek_api_key:
        raise ValueError("DEEPSEEK_API_KEY is not configured")

    user_text = payload.message or "请提供A股策略分析建议。"
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]

    for _ in range(5):
        data = await _call_api(messages, tools=TOOL_DEFINITIONS)
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        finish_reason = choice.get("finish_reason", "")

        if msg.get("tool_calls"):
            assistant_message = {
                "role": "assistant",
                "content": msg.get("content") or "",
                "tool_calls": msg["tool_calls"],
            }
            if msg.get("reasoning_content"):
                assistant_message["reasoning_content"] = msg["reasoning_content"]
            messages.append(assistant_message)

            for tc in msg["tool_calls"]:
                func = tc.get("function", {})
                tool_name = func.get("name", "")
                try:
                    tool_args = json.loads(func.get("arguments", "{}"))
                except json.JSONDecodeError:
                    tool_args = {}
                logger.info(f"AI tool call: {tool_name}({tool_args})")
                try:
                    result = await asyncio.wait_for(
                        execute_tool(tool_name, tool_args),
                        timeout=30,
                    )
                except asyncio.TimeoutError:
                    result = f"工具 {tool_name} 执行超时，数据源可能暂时不可用。"
                except Exception as exc:
                    result = f"工具执行失败: {exc}"
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": result,
                    }
                )
            continue

        text = _extract_text(data)
        if text:
            return text
        if finish_reason == "stop" and not text:
            return "AI 响应为空，请换个方式提问。"

    return "AI 工具调用超出限制，请稍后重试。"
