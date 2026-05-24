from typing import Any, Optional

from pydantic import BaseModel


class AttachmentDto(BaseModel):
    fileKey: Optional[str] = None
    fileUrl: str
    fileName: Optional[str] = None
    mimeType: str


class SelectedComponentDto(BaseModel):
    id: int | str
    type: Optional[str] = None


class ChatRequest(BaseModel):
    conversationId: int
    variableParams: Optional[dict[str, Any]] = None
    message: Optional[str] = None
    attachments: Optional[list[AttachmentDto]] = None
    debug: Optional[bool] = False
    sandboxId: Optional[int] = None
    selectedComponents: Optional[list[SelectedComponentDto]] = None
    skillIds: Optional[list[int]] = None
    filterSensitive: Optional[bool] = None
    modelId: Optional[int] = None
