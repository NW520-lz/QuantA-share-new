from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.deps import get_current_user
from app.models.review_log import ReviewLog
from app.schemas.review import ReviewLogCreate, ReviewLogOut

router = APIRouter()


@router.get("", response_model=list[ReviewLogOut])
async def list_logs(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> list[ReviewLog]:
    result = await db.execute(
        select(ReviewLog)
        .where(ReviewLog.user_id == user.id)
        .order_by(ReviewLog.log_date.desc())
    )
    return list(result.scalars().all())


@router.post("", response_model=ReviewLogOut)
async def create_log(
    payload: ReviewLogCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> ReviewLog:
    log = ReviewLog(
        user_id=user.id,
        log_date=payload.log_date,
        title=payload.title,
        content=payload.content,
        extra_data=payload.metadata,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


@router.delete("/{log_id}")
async def delete_log(
    log_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    import uuid

    result = await db.execute(
        select(ReviewLog).where(
            ReviewLog.id == uuid.UUID(log_id), ReviewLog.user_id == user.id
        )
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    await db.delete(log)
    await db.commit()
    return {"status": "deleted"}
