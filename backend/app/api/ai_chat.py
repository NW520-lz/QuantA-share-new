from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.deps import get_current_user
from app.schemas.ai import ChatRequest
from app.services.ai_service import stream_ai
from app.services.system_log import write_system_log

router = APIRouter()


@router.post("/chat/{conversation_id}")
async def chat(
    conversation_id: int,
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> StreamingResponse:
    try:
        user_id = str(user.id)
        prompt = (payload.message or "").strip()
        if prompt:
            await write_system_log(
                db,
                user_id=user_id,
                channel="ai",
                level="INFO",
                source="ai.chat",
                message=f"用户发起对话: {prompt[:80]}",
                context={"conversation_id": conversation_id},
            )

        async def _stream():
            try:
                async for chunk in stream_ai(conversation_id, payload):
                    yield chunk
                await write_system_log(
                    db,
                    user_id=user_id,
                    channel="ai",
                    level="SUCCESS",
                    source="ai.chat",
                    message="AI 对话完成",
                    context={"conversation_id": conversation_id},
                )
            except Exception as exc:  # pragma: no cover - defensive path for stream layer
                await write_system_log(
                    db,
                    user_id=user_id,
                    channel="ai",
                    level="ERROR",
                    source="ai.chat",
                    message=f"AI 对话异常: {exc}",
                    context={"conversation_id": conversation_id},
                )
                raise

        return StreamingResponse(_stream(), media_type="text/event-stream")
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
