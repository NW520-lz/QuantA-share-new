import hashlib
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.deps import get_current_user
from app.models.billing_plan import BillingPlan
from app.models.payment_order import PaymentOrder
from app.models.user import User
from app.models.user_subscription import UserSubscription
from app.schemas.billing import (
    AdminConfirmRequest,
    BillingPlanListResponse,
    BillingPlanOut,
    CreateOrderRequest,
    DonationOut,
    DonationRequest,
    PaymentOrderOut,
    SubscriptionOut,
)
from app.services.billing.pricing import TIER_FREE, recommended_pricing

router = APIRouter()


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _md5(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def _create_sign(
    merchant_num: str, order_no: str, amount_yuan: str, notify_url: str, secret: str
) -> str:
    """创建订单签名：MD5(商户号+订单号+金额+notifyUrl+密钥)"""
    return _md5(merchant_num + order_no + amount_yuan + notify_url + secret)


def _notify_sign(
    state: str, merchant_num: str, order_no: str, amount_yuan: str, secret: str
) -> str:
    """回调验签：MD5(state+商户号+订单号+金额+密钥)"""
    return _md5(state + merchant_num + order_no + amount_yuan + secret)


def _fen_to_yuan(fen: int) -> str:
    """分转元，保留2位小数字符串，如 2990 → '29.90'"""
    return f"{fen / 100:.2f}"


def _order_no_from_uuid(uuid_val) -> str:
    """UUID 去掉横线得到 32 位纯字母数字订单号"""
    return str(uuid_val).replace("-", "")


async def _ensure_default_plans(db: AsyncSession) -> list[BillingPlan]:
    note, plan_defs = recommended_pricing()
    _ = note
    existing = (await db.execute(select(BillingPlan))).scalars().all()
    by_code = {p.code: p for p in existing}
    for p in plan_defs:
        row = by_code.get(p["code"])
        if row:
            row.name = p["name"]
            row.price_cny = p["price_cny"]
            row.period_days = p["period_days"]
            row.features = p["features"]
            row.is_active = True
        else:
            db.add(BillingPlan(**p, is_active=True))
    await db.commit()
    return (
        (await db.execute(select(BillingPlan).where(BillingPlan.is_active.is_(True))))
        .scalars()
        .all()
    )


async def _active_subscription(db: AsyncSession, user_id) -> UserSubscription | None:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(UserSubscription)
        .where(
            and_(
                UserSubscription.user_id == user_id,
                UserSubscription.status == "active",
                UserSubscription.starts_at <= now,
                or_(
                    UserSubscription.ends_at.is_(None), UserSubscription.ends_at >= now
                ),
            )
        )
        .order_by(UserSubscription.ends_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _get_plan_tier(db: AsyncSession, plan_code: str) -> str:
    plan = (
        await db.execute(select(BillingPlan).where(BillingPlan.code == plan_code))
    ).scalar_one_or_none()
    if plan and plan.features:
        return plan.features.get("tier", TIER_FREE)
    return TIER_FREE


async def _call_zhifufm(
    order_no: str,
    amount_fen: int,
    notify_url: str,
    subject: str = "",
    return_url: str = "",
) -> str:
    """调用支付FM创建订单，返回 payUrl。失败时抛出 HTTPException。"""
    if not settings.zhifufm_api_url or not settings.zhifufm_merchant_num:
        raise HTTPException(status_code=503, detail="支付接口未配置，请联系管理员")

    # notifyUrl 必须是公网地址，本地地址会被支付FM拒绝
    if any(x in notify_url for x in ("127.0.0.1", "localhost", "0.0.0.0")):
        raise HTTPException(
            status_code=503,
            detail="支付回调地址不能是本地地址，请在 .env 中配置公网 ZHIFUFM_NOTIFY_URL"
        )

    amount_yuan = _fen_to_yuan(amount_fen)
    sign = _create_sign(
        settings.zhifufm_merchant_num,
        order_no,
        amount_yuan,
        notify_url,
        settings.zhifufm_secret,
    )
    params = {
        "merchantNum": settings.zhifufm_merchant_num,
        "orderNo": order_no,
        "amount": amount_yuan,
        "notifyUrl": notify_url,
        "payType": settings.zhifufm_pay_type,
        "returnType": "json",
        "sign": sign,
    }
    if subject:
        params["subject"] = subject
    if return_url:
        params["returnUrl"] = return_url

    url = f"{settings.zhifufm_api_url.rstrip('/')}/startOrder"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            url,
            params=params,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=502, detail=f"支付接口异常: HTTP {resp.status_code}"
        )

    data = resp.json()
    if not data.get("success"):
        raise HTTPException(status_code=400, detail=data.get("msg", "支付接口返回失败"))

    return data["data"]["payUrl"]


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------


@router.get("/plans", response_model=BillingPlanListResponse)
async def list_plans(db: AsyncSession = Depends(get_db)) -> BillingPlanListResponse:
    note, _ = recommended_pricing()
    plans = await _ensure_default_plans(db)
    return BillingPlanListResponse(
        pricing_note=note,
        plans=[
            BillingPlanOut(
                code=p.code,
                name=p.name,
                price_cny=p.price_cny,
                period_days=p.period_days,
                features=p.features,
                is_active=p.is_active,
            )
            for p in plans
        ],
    )


@router.post("/orders", response_model=PaymentOrderOut)
async def create_order(
    payload: CreateOrderRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaymentOrderOut:
    # 先确保默认套餐存在，再重新查询（避免同一 session 缓存问题）
    await _ensure_default_plans(db)
    await db.commit()  # 确保写入刷新

    plan = (
        await db.execute(
            select(BillingPlan).where(
                and_(
                    BillingPlan.code == payload.plan_code,
                    BillingPlan.is_active.is_(True),
                )
            )
        )
    ).scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail=f"套餐 {payload.plan_code!r} 不存在，请刷新页面重试")

    # 先落库，拿到 UUID 作为订单号
    order = PaymentOrder(
        user_id=user.id,
        plan_code=plan.code,
        amount_cny=plan.price_cny,
        gateway="zhifufm",
        status="pending",
        extra={"plan_name": plan.name},
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    order_no = _order_no_from_uuid(order.id)
    notify_url = (
        settings.zhifufm_notify_url
        or f"{settings.billing_public_base_url}/api/v1/billing/notify"
    )
    # returnUrl：优先用 FRONTEND_BASE_URL，没配就用 BILLING_PUBLIC_BASE_URL
    frontend_base = settings.frontend_base_url or settings.billing_public_base_url
    return_url = f"{frontend_base}/选股看板.html?paid=1"

    pay_url = await _call_zhifufm(
        order_no, plan.price_cny, notify_url, subject=plan.name, return_url=return_url
    )
    order.payment_url = pay_url
    await db.commit()

    return PaymentOrderOut(
        order_id=str(order.id),
        plan_code=order.plan_code,
        amount_cny=order.amount_cny,
        status=order.status,
        gateway=order.gateway,
        pay_url=pay_url,
        created_at=order.created_at,
    )


@router.post("/donate", response_model=DonationOut)
async def create_donation(
    payload: DonationRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DonationOut:
    """打赏接口，留言后有机会获得一个月道友期。"""
    order = PaymentOrder(
        user_id=user.id,
        plan_code="donation",
        amount_cny=payload.amount_cny,
        gateway="zhifufm",
        status="pending",
        extra={"message": payload.message, "type": "donation"},
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    order_no = _order_no_from_uuid(order.id)
    notify_url = (
        settings.zhifufm_notify_url
        or f"{settings.billing_public_base_url}/api/v1/billing/notify"
    )
    return_url = f"{settings.frontend_base_url or settings.billing_public_base_url}/选股看板.html?donated=1"
    amount_yuan = _fen_to_yuan(payload.amount_cny)

    pay_url = await _call_zhifufm(
        order_no,
        payload.amount_cny,
        notify_url,
        subject="打赏支持",
        return_url=return_url,
    )
    order.payment_url = pay_url
    await db.commit()

    return DonationOut(
        order_id=str(order.id),
        amount_cny=order.amount_cny,
        amount_yuan=amount_yuan,
        message=payload.message,
        status=order.status,
        pay_url=pay_url,
        created_at=order.created_at,
    )


@router.get("/notify")
@router.post("/notify")
async def payment_notify(
    request: Request, db: AsyncSession = Depends(get_db)
) -> PlainTextResponse:
    """支付FM 回调通知接口（GET/POST 均支持）。
    签名验证：MD5(state + merchantNum + orderNo + amount + 密钥)
    """
    params = dict(request.query_params)
    if request.method == "POST":
        form = await request.form()
        params.update(dict(form))

    order_no = params.get("orderNo", "")
    state = params.get("state", "")
    merchant_num = params.get("merchantNum", "")
    amount_yuan = params.get("amount", "")
    sign_recv = params.get("sign", "")

    # 验签
    expected = _notify_sign(
        state,
        settings.zhifufm_merchant_num,
        order_no,
        amount_yuan,
        settings.zhifufm_secret,
    )
    if merchant_num != settings.zhifufm_merchant_num or expected != sign_recv:
        return PlainTextResponse("fail")

    if state != "1":
        return PlainTextResponse("success")  # 非成功状态，忽略但返回 success

    # 通过 orderNo（UUID 去横线）找到订单
    try:
        order_uuid = UUID(
            order_no[:8]
            + "-"
            + order_no[8:12]
            + "-"
            + order_no[12:16]
            + "-"
            + order_no[16:20]
            + "-"
            + order_no[20:]
        )
    except Exception:
        return PlainTextResponse("fail")

    order = (
        await db.execute(select(PaymentOrder).where(PaymentOrder.id == order_uuid))
    ).scalar_one_or_none()
    if not order:
        return PlainTextResponse("fail")

    if order.status == "paid":
        return PlainTextResponse("success")  # 幂等

    now = datetime.now(timezone.utc)
    order.status = "paid"
    order.paid_at = now
    order.extra = {
        **(order.extra or {}),
        "platform_order_no": params.get("platformOrderNo", ""),
        "actual_pay": params.get("actualPayAmount", ""),
    }

    if order.plan_code != "donation":
        plan = (
            await db.execute(
                select(BillingPlan).where(BillingPlan.code == order.plan_code)
            )
        ).scalar_one_or_none()
        if plan:
            sub = UserSubscription(
                user_id=order.user_id,
                plan_code=order.plan_code,
                status="active",
                starts_at=now,
                ends_at=now + timedelta(days=plan.period_days),
            )
            db.add(sub)
    else:
        order.status = "paid_donation"

    await db.commit()
    return PlainTextResponse("success")


@router.get("/subscription", response_model=SubscriptionOut)
async def get_subscription(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SubscriptionOut:
    active = await _active_subscription(db, user.id)
    if active:
        tier = await _get_plan_tier(db, active.plan_code)
        return SubscriptionOut(
            is_subscribed=True,
            plan_code=active.plan_code,
            tier=tier,
            status=active.status,
            starts_at=active.starts_at,
            ends_at=active.ends_at,
        )
    now = datetime.now(timezone.utc)
    trial_valid = bool(user.trial_ends_at and user.trial_ends_at >= now)
    return SubscriptionOut(
        is_subscribed=trial_valid,
        plan_code="trial" if trial_valid else None,
        tier=TIER_FREE,
        status="active" if trial_valid else "expired",
        starts_at=None,
        ends_at=user.trial_ends_at,
    )


@router.post("/admin/confirm", response_model=dict)
async def admin_confirm_order(
    payload: AdminConfirmRequest,
    x_admin_secret: str | None = Header(default=None, alias="X-Admin-Secret"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """管理员手动确认打赏订单，决定是否赠送道友期。"""
    if not x_admin_secret or x_admin_secret != settings.admin_secret:
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        order_uuid = UUID(payload.order_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid order id") from exc

    order = (
        await db.execute(select(PaymentOrder).where(PaymentOrder.id == order_uuid))
    ).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.plan_code != "donation":
        raise HTTPException(status_code=400, detail="只有打赏订单需要手动确认")
    if order.status not in ("paid_donation",):
        raise HTTPException(
            status_code=400, detail=f"订单状态为 {order.status}，无法确认"
        )

    grant_days = payload.grant_days or 30
    now = datetime.now(timezone.utc)
    sub = UserSubscription(
        user_id=order.user_id,
        plan_code="daoyou_monthly",
        status="active",
        starts_at=now,
        ends_at=now + timedelta(days=grant_days),
    )
    db.add(sub)
    order.status = "donation_granted"
    await db.commit()
    return {"message": f"已赠送 {grant_days} 天道友期"}


@router.get("/admin/pending-orders", response_model=list[dict])
async def admin_list_pending(
    x_admin_secret: str | None = Header(default=None, alias="X-Admin-Secret"),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """管理员查看待处理的打赏订单。"""
    if not x_admin_secret or x_admin_secret != settings.admin_secret:
        raise HTTPException(status_code=403, detail="Forbidden")

    orders = (
        (
            await db.execute(
                select(PaymentOrder)
                .where(PaymentOrder.status == "paid_donation")
                .order_by(PaymentOrder.created_at.desc())
            )
        )
        .scalars()
        .all()
    )

    return [
        {
            "order_id": str(o.id),
            "user_id": str(o.user_id),
            "amount_yuan": _fen_to_yuan(o.amount_cny),
            "message": (o.extra or {}).get("message", ""),
            "status": o.status,
            "created_at": o.created_at.isoformat(),
        }
        for o in orders
    ]
