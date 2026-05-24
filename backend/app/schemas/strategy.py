from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, ConfigDict


class StrategyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    mode: str = Field(default="swing", max_length=32)
    params: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class StrategyUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = None
    mode: Optional[str] = Field(default=None, max_length=32)
    params: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None


class StrategyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    name: str
    description: Optional[str]
    mode: str
    params: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime
