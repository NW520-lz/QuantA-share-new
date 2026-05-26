import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.user import User
from app.models.billing_plan import BillingPlan
from app.models.user_subscription import UserSubscription


async def upgrade_user():
    email = "2817197921@qq.com"
    async with AsyncSessionLocal() as db:
        user = (
            await db.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if not user:
            print(f"未找到用户: {email}，正在本地创建...")
            user = User(
                id=uuid.uuid4(),
                email=email,
                email_verified=True,
                password_hash=get_password_hash("2817197921"),
                role="user",
                trial_ends_at=datetime.now(timezone.utc) + timedelta(days=365),
            )
            db.add(user)
            await db.flush()
            print(f"已创建用户: {email} / 密码: 510524")
        else:
            user.password_hash = get_password_hash("510524")
            print(f"密码已更新为: 510524")

        plan_code = "qianbei_yearly"
        plan = (
            await db.execute(select(BillingPlan).where(BillingPlan.code == plan_code))
        ).scalar_one_or_none()
        if not plan:
            plan = BillingPlan(
                code=plan_code,
                name="前辈期",
                price_cny=19900,
                period_days=365,
                features={
                    "tier": "qianbei",
                    "all_features": True,
                    "description": "解锁全部功能，年付",
                },
                is_active=True,
            )
            db.add(plan)
            await db.flush()
            print(f"已创建计划: {plan_code}")

        now = datetime.now(timezone.utc)
        sub = UserSubscription(
            user_id=user.id,
            plan_code=plan_code,
            status="active",
            starts_at=now,
            ends_at=now + timedelta(days=365),
        )
        db.add(sub)
        user.trial_ends_at = now + timedelta(days=365)
        await db.commit()
        print(f"已升级 {email} 为 前辈期 (qianbei_yearly)，有效期至 {sub.ends_at}")


asyncio.run(upgrade_user())
