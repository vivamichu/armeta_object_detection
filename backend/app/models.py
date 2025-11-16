from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class DocumentStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    succeeded = "succeeded"
    failed = "failed"
    upload_failed = "upload_failed"
    processing_failed = "processing_failed"


class Document(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, index=True)
    file_name: str
    stored_path: str
    status: DocumentStatus = Field(default=DocumentStatus.pending)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    detections: list[dict[str, Any]] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    failure_reason: str | None = None


class Detection(SQLModel):
    label: str
    confidence: float
    bounding_box: tuple[float, float, float, float]
    page: int | None = None
