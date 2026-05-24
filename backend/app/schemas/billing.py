from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BillingPlanOut(BaseModel):
    code: str
    name: str
    price_cny: int   # 单位：分，前端显示时除以100
    period_days: int
    features: dict[str, Any]
    is_active: bool


class BillingPlanListResponse(BaseModel):
    pricing_note: str
    plans: list[BillingPlanOut]


class CreateOrderRequest(BaseModel):
    plan_code: str = Field(min_length=2, max_length=64)


class PaymentOrderOut(BaseModel):
    order_id: str
    plan_code: str
    amount_cny: int   # 单位：分
    status: str
    gateway: str
    pay_url: str | None = None   # 支付FM 返回的支付链接，前端直接跳转
    created_at: datetime


class SubscriptionOut(BaseModel):
    is_subscribed: bool
    plan_code: str | None = None
    tier: str | None = None   # lüyi / daoyou / qianbei
    status: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class DonationRequest(BaseModel):
    amount_cny: int = Field(ge=100, description="打赏金额（分），最低1元")
    message: str = Field(default="", max_length=200, description="留言")


class DonationOut(BaseModel):
    order_id: str
    amount_cny: int
    amount_yuan: str
    message: str
    status: str
    pay_url: str | None = None
    created_at: datetime


class AdminConfirmRequest(BaseModel):
    order_id: str
    grant_days: int | None = None   # 打赏订单赠送天数，默认30
