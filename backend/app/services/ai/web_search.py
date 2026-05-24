from __future__ import annotations

import json
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger("web_search")

TAVILY_URL = "https://api.tavily.com/search"
BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"


async def search_tavily(query: str, max_results: int = 5) -> str:
    if not settings.tavily_api_key:
        return "Tavily API key 未配置"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                TAVILY_URL,
                json={
                    "api_key": settings.tavily_api_key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "basic",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        results = data.get("results", [])
        if not results:
            return f"未找到关于 '{query}' 的搜索结果。"

        answer = data.get("answer", "")
        lines = []
        if answer:
            lines.append(f"AI 摘要: {answer}\n")

        lines.append("搜索结果:")
        for i, r in enumerate(results[:max_results], 1):
            title = r.get("title", "")
            url = r.get("url", "")
            content = (r.get("content") or "")[:300]
            lines.append(f"{i}. {title}\n   {url}\n   {content}")
        return "\n".join(lines)

    except Exception as exc:
        logger.error(f"Tavily search failed: {exc}")
        return f"搜索失败: {exc}"


async def search_brave(query: str, max_results: int = 5) -> str:
    if not settings.brave_api_key:
        return "Brave API key 未配置"

    try:
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": settings.brave_api_key,
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                BRAVE_URL,
                headers=headers,
                params={"q": query, "count": max_results},
            )
            resp.raise_for_status()
            data = resp.json()

        web_results = data.get("web", {}).get("results", [])
        if not web_results:
            return f"Brave 搜索未找到关于 '{query}' 的结果。"

        lines = ["Brave 搜索结果:"]
        for i, r in enumerate(web_results[:max_results], 1):
            title = r.get("title", "")
            url = r.get("url", "")
            description = (r.get("description") or "")[:300]
            lines.append(f"{i}. {title}\n   {url}\n   {description}")
        return "\n".join(lines)

    except Exception as exc:
        logger.error(f"Brave search failed: {exc}")
        return f"Brave 搜索失败: {exc}"


async def web_search(query: str, max_results: int = 5) -> str:
    result = await search_tavily(query, max_results)
    if "搜索失败" in result or "未配置" in result:
        result = await search_brave(query, max_results)
    return result
