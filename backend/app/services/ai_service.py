import json
from typing import AsyncGenerator

from app.schemas.ai import ChatRequest
from app.services.ai.deepseek_client import chat_deepseek
from app.services.ai.github_models_client import chat_github_models
from app.services.ai.nuwax_client import stream_nuwax


def _sse(event_type: str, data: dict) -> bytes:
    payload = {"eventType": event_type, "data": data}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")


async def stream_ai(
    conversation_id: int, payload: ChatRequest
) -> AsyncGenerator[bytes, None]:
    deepseek_err: Exception | None = None
    github_err: Exception | None = None
    nuwax_err: Exception | None = None

    try:
        yield _sse("SYSTEM_LOG", {"text": "AI正在分析（DeepSeek）..."})
        text = await chat_deepseek(payload)
        yield _sse("MESSAGE", {"text": text})
        yield _sse("FINAL_RESULT", {"outputText": text})
        return
    except Exception as exc:
        deepseek_err = exc
        yield _sse("SYSTEM_LOG", {"text": "DeepSeek不可用，切换到GitHub Models..."})

    try:
        yield _sse("SYSTEM_LOG", {"text": "AI正在分析（GitHub Models）..."})
        text = await chat_github_models(payload)
        yield _sse("MESSAGE", {"text": text})
        yield _sse("FINAL_RESULT", {"outputText": text})
        return
    except Exception as exc:
        github_err = exc
        yield _sse("SYSTEM_LOG", {"text": "GitHub Models不可用，尝试Nuwax..."})

    try:
        async for chunk in stream_nuwax(conversation_id, payload):
            yield chunk
        return
    except Exception as exc:
        nuwax_err = exc

    detail = f"AI调用失败。deepseek={deepseek_err}; github_models={github_err}; nuwax={nuwax_err}"
    yield _sse("ERROR", {"text": detail})
    message = "AI 服务暂时不可用，请稍后重试。"
    if "429" in str(deepseek_err) or "429" in str(github_err):
        message = "AI 服务当前请求过多，已被上游限流，请稍后再试。"
    yield _sse("FINAL_RESULT", {"outputText": message})


__all__ = ["stream_ai"]
