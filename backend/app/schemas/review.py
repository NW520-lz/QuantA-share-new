from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, field_validator


class ReviewLogCreate(BaseModel):
    log_date: date
    title: Optional[str] = None
    content: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReviewLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    user_id: str
    log_date: date
    title: Optional[str] = None
    content: Optional[str] = None
    metadata: dict[str, Any] = Field(validation_alias="extra_data")
    created_at: datetime

    @field_validator("id", "user_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v: Any) -> str:
        if isinstance(v, UUID):
            return str(v)
        return v
