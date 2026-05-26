import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token, get_password_hash, verify_password
from app.deps import get_current_user
from app.models.email_verification_code import EmailVerificationCode
from app.models.user import User
from app.models.user_subscription import UserSubscription
from app.schemas.auth import (
    LoginRequest,
    RegisterByEmailRequest,
    RegisterRequest,
    SendEmailCodeRequest,
    Token,
    UserOut,
)
from app.services.email_service import send_verification_email

router = APIRouter()


async def _find_user_by_login(db: AsyncSession, login: str) -> User | None:
    return (
        await db.execute(
            select(User).where(or_(User.uid == login, User.phone == login, User.email == login))
        )
    ).scalar_one_or_none()


def _hash_code(email: str, purpose: str, code: str) -> str:
    payload = f"{email.lower()}:{purpose}:{code}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def _get_active_subscription(db: AsyncSession, user_id: str) -> UserSubscription | None:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(UserSubscription)
        .where(
            and_(
                UserSubscription.user_id == user_id,
                UserSubscription.status == "active",
                UserSubscription.starts_at <= now,
                or_(UserSubscription.ends_at.is_(None), UserSubscription.ends_at >= now),
            )
        )
        .order_by(UserSubscription.starts_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


@router.post("/register", response_model=UserOut)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> User:
    if not payload.uid and not payload.phone and not payload.email:
        raise HTTPException(status_code=400, detail="uid, phone, or email is required")

    conditions = []
    if payload.uid:
        conditions.append(User.uid == payload.uid)
    if payload.phone:
        conditions.append(User.phone == payload.phone)
    if payload.email:
        conditions.append(User.email == payload.email)

    if conditions:
        existing = (await db.execute(select(User).where(or_(*conditions)))).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="User already exists")

    user = User(
        uid=payload.uid,
        phone=payload.phone,
        email=payload.email,
        email_verified=bool(payload.email),
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=7),
        password_hash=get_password_hash(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/email/send-code")
async def send_email_code(payload: SendEmailCodeRequest, db: AsyncSession = Depends(get_db)) -> dict:
    email = payload.email.lower()
    if payload.purpose == "register":
        existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Email already registered")

    now = datetime.now(timezone.utc)
    latest = (
        await db.execute(
            select(EmailVerificationCode)
            .where(
                and_(
                    EmailVerificationCode.email == email,
                    EmailVerificationCode.purpose == payload.purpose,
                )
            )
            .order_by(EmailVerificationCode.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest and (now - latest.created_at).total_seconds() < 60:
        retry_after = 60 - int((now - latest.created_at).total_seconds())
        raise HTTPException(status_code=429, detail=f"请在 {retry_after} 秒后再试")

    code = f"{secrets.randbelow(1000000):06d}"
    expires_at = now + timedelta(minutes=10)

    record = EmailVerificationCode(
        email=email,
        purpose=payload.purpose,
        code_hash=_hash_code(email, payload.purpose, code),
        expires_at=expires_at,
    )
    db.add(record)
    await db.commit()

    try:
        await send_verification_email(email, code)
    except Exception as exc:
        logger.error(f"Send email failed: {exc}", exc_info=True)
        raise HTTPException(status_code=502, detail="邮件发送失败，请稍后再试") from exc

    return {"message": "Verification code sent", "expires_at": expires_at, "retry_after": 60}


@router.post("/email/register", response_model=UserOut)
async def register_by_email(payload: RegisterByEmailRequest, db: AsyncSession = Depends(get_db)) -> User:
    email = payload.email.lower()
    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    code_row = (
        await db.execute(
            select(EmailVerificationCode)
            .where(
                and_(
                    EmailVerificationCode.email == email,
                    EmailVerificationCode.purpose == "register",
                    EmailVerificationCode.consumed_at.is_(None),
                )
            )
            .order_by(EmailVerificationCode.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if not code_row:
        raise HTTPException(status_code=400, detail="Verification code not found")
    if code_row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Verification code expired")
    if code_row.attempts >= 5:
        raise HTTPException(status_code=429, detail="Too many attempts")

    code_row.attempts += 1
    expected = _hash_code(email, "register", payload.code)
    if not hmac.compare_digest(expected, code_row.code_hash):
        await db.commit()
        raise HTTPException(status_code=400, detail="Invalid verification code")

    code_row.consumed_at = datetime.now(timezone.utc)
    user = User(
        uid=payload.uid,
        email=email,
        email_verified=True,
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=7),
        password_hash=get_password_hash(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


_login_attempts: dict[str, tuple[int, float]] = {}
_MAX_ATTEMPTS = 5
_WINDOW_SECONDS = 300


def _check_login_rate_limit(login: str) -> None:
    now = time.time()
    attempts, first_time = _login_attempts.get(login, (0, now))
    if now - first_time > _WINDOW_SECONDS:
        _login_attempts[login] = (1, now)
        return
    if attempts >= _MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"登录尝试次数过多，请 {_WINDOW_SECONDS // 60} 分钟后重试",
        )
    _login_attempts[login] = (attempts + 1, first_time)


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> Token:
    _check_login_rate_limit(payload.login)
    user = await _find_user_by_login(db, payload.login)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    subscription = await _get_active_subscription(db, str(user.id))
    now = datetime.now(timezone.utc)
    
    # 确保 trial_ends_at 比较安全
    trial_valid = False
    if user.trial_ends_at:
        trial_at = user.trial_ends_at
        if trial_at.tzinfo is None:
            trial_at = trial_at.replace(tzinfo=timezone.utc)
        trial_valid = trial_at >= now

    token = create_access_token(str(user.id))
    return Token(
        access_token=token,
        is_subscribed=bool(subscription) or trial_valid,
        plan_code=subscription.plan_code if subscription else ("trial" if trial_valid else None),
        trial_ends_at=user.trial_ends_at,
    )


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
