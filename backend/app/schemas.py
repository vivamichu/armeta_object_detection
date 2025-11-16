from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from .models import DocumentStatus


class DetectionPayload(BaseModel):
    label: str
    confidence: float
    bounding_box: tuple[float, float, float, float]
    page: int | None = None
    page_width: float | None = None
    page_height: float | None = None


class DocumentRead(BaseModel):
    id: str
    file_name: str
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime
    detections: list[DetectionPayload] | None = None
    failure_reason: str | None = None
    download_url: str | None = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentRead]


class UploadResponse(DocumentListResponse):
    pass
