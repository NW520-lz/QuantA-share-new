from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator
from pydantic import ConfigDict


class RegisterRequest(BaseModel):
    uid: Optional[str] = Field(default=None, max_length=64)
    phone: Optional[str] = Field(default=None, max_length=32)
    email: Optional[EmailStr] = None
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    login: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=6, max_length=128)


class SendEmailCodeRequest(BaseModel):
    email: EmailStr
    purpose: str = Field(default="register", max_length=32)


class RegisterByEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=8)
    password: str = Field(min_length=6, max_length=128)
    uid: Optional[str] = Field(default=None, max_length=64)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_subscribed: bool = False
    plan_code: Optional[str] = None
    trial_ends_at: Optional[datetime] = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    uid: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    email_verified: bool = False
    role: str
    trial_ends_at: Optional[datetime] = None
    created_at: datetime

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id(cls, v: Any) -> str:
        if isinstance(v, UUID):
            return str(v)
        return v
