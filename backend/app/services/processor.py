from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from sqlmodel import Session

from ..config import get_settings
from ..database import engine
from ..models import Document, DocumentStatus
from .ml_client import DigitalInspectorClient, detection_from_result

settings = get_settings()
_client: DigitalInspectorClient | None = None


def get_client() -> DigitalInspectorClient:
    global _client
    if _client is None:
        _client = DigitalInspectorClient()
    return _client


async def process_document(document_id: str) -> None:
    await asyncio.to_thread(_update_status, document_id, DocumentStatus.processing, None)

    try:
        stored_path = await asyncio.to_thread(_get_stored_path, document_id)
        detections = await get_client().analyze(Path(stored_path))
        await asyncio.to_thread(
            _complete_document,
            document_id,
            [detection_from_result(d) for d in detections],
        )
    except Exception as exc:  # noqa: BLE001
        await asyncio.to_thread(_update_status, document_id, DocumentStatus.processing_failed, str(exc))


def _get_stored_path(document_id: str) -> str:
    with Session(engine) as session:
        document = session.get(Document, document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found")
        return document.stored_path


def _complete_document(document_id: str, detections: list[dict]) -> None:
    with Session(engine) as session:
        document = session.get(Document, document_id)
        if not document:
            return
        document.status = DocumentStatus.succeeded
        document.detections = detections
        document.updated_at = datetime.utcnow()
        session.add(document)
        session.commit()


def _update_status(document_id: str, status: DocumentStatus, reason: str | None) -> None:
    with Session(engine) as session:
        document = session.get(Document, document_id)
        if not document:
            return
        document.status = status
        document.failure_reason = reason
        document.updated_at = datetime.utcnow()
        session.add(document)
        session.commit()
