import uuid
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.billing_plan import BillingPlan
from app.models.user import User
from app.models.user_subscription import UserSubscription
from app.services.billing.pricing import TIER_FREE, TIER_RANK


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        user_uuid = uuid.UUID(user_id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


async def get_user_tier(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> str:
    """返回当前用户的会员等级：lüyi / daoyou / qianbei"""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(UserSubscription)
        .where(
            and_(
                UserSubscription.user_id == user.id,
                UserSubscription.status == "active",
                UserSubscription.starts_at <= now,
                or_(UserSubscription.ends_at.is_(None), UserSubscription.ends_at >= now),
            )
        )
        .order_by(UserSubscription.ends_at.desc())
        .limit(1)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        return TIER_FREE

    plan = (await db.execute(select(BillingPlan).where(BillingPlan.code == sub.plan_code))).scalar_one_or_none()
    if plan and plan.features:
        return plan.features.get("tier", TIER_FREE)
    return TIER_FREE


def require_tier(min_tier: str):
    """依赖注入工厂：要求用户至少达到指定等级，否则返回 403。"""
    async def _check(tier: str = Depends(get_user_tier)) -> str:
        if TIER_RANK.get(tier, 0) < TIER_RANK.get(min_tier, 0):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要{min_tier}等级或以上，请升级会员",
            )
        return tier
    return _check
