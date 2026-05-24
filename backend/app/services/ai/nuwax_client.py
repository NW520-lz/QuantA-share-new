from typing import AsyncGenerator

import httpx

from app.core.config import settings
from app.schemas.ai import ChatRequest


async def stream_nuwax(
    conversation_id: int, payload: ChatRequest
) -> AsyncGenerator[bytes, None]:
    if not settings.nuwax_api_key:
        raise ValueError("NUWAX_API_KEY is not configured")

    url = f"{settings.nuwax_base_url}/api/v1/chat/{conversation_id}"
    headers = {
        "Authorization": f"Bearer {settings.nuwax_api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    payload_dict = payload.model_dump()
    if not payload_dict.get("selectedComponents") and settings.nuwax_agent_id:
        payload_dict["selectedComponents"] = [
            {"id": settings.nuwax_agent_id, "type": "Agent"}
        ]

    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "POST", url, headers=headers, json=payload_dict
        ) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                yield chunk
