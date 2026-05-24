from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, ConfigDict


class SystemSettingsPayload(BaseModel):
    settings: dict[str, Any] = Field(default_factory=dict)


class SystemSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    settings: dict[str, Any]
    updated_at: datetime


class SystemStatus(BaseModel):
    server_time: datetime
