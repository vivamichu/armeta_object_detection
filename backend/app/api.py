from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Sequence

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from .config import get_settings
from .database import get_session
from .models import Document, DocumentStatus
from .schemas import DocumentListResponse, DocumentRead, UploadResponse
from .services import storage
from .services.processor import process_document

router = APIRouter()
settings = get_settings()


@router.post("/documents/upload", response_model=UploadResponse, status_code=202)
async def upload_documents(
    request: Request,
    files: list[UploadFile] = File(...),
    session: Session = Depends(get_session),
) -> UploadResponse:
    if not files:
        raise HTTPException(status_code=400, detail="At least one PDF is required.")

    for upload in files:
        if not upload.filename or not upload.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    persisted: list[Document] = []
    for upload in files:
        document = Document(file_name=upload.filename or "document.pdf", stored_path="")
        session.add(document)
        session.commit()
        session.refresh(document)

        try:
            path = await storage.save_upload(document.id, upload)
        except Exception as exc:  # noqa: BLE001
            document.status = DocumentStatus.upload_failed
            document.failure_reason = str(exc)
            document.updated_at = datetime.utcnow()
            session.add(document)
            session.commit()
            session.refresh(document)
            persisted.append(document)
            continue

        document.stored_path = str(path)
        document.status = DocumentStatus.pending
        document.failure_reason = None
        document.updated_at = datetime.utcnow()
        session.add(document)
        session.commit()
        session.refresh(document)

        asyncio.create_task(process_document(document.id))
        persisted.append(document)

    return UploadResponse(documents=_serialize_documents(request, persisted))


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(request: Request, session: Session = Depends(get_session)) -> DocumentListResponse:
    statement = select(Document).order_by(Document.created_at.desc())
    documents = session.exec(statement).all()
    return DocumentListResponse(documents=_serialize_documents(request, documents))


@router.get("/documents/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: str,
    request: Request,
    session: Session = Depends(get_session),
) -> DocumentRead:
    document = session.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return _serialize_document(request, document)


@router.get("/documents/{document_id}/file", response_class=FileResponse)
async def download_document(
    document_id: str,
    download: bool = Query(default=False),
    session: Session = Depends(get_session),
) -> FileResponse:
    document = session.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    disposition = "attachment" if download else "inline"
    return FileResponse(
        path=document.stored_path,
        filename=document.file_name,
        media_type="application/pdf",
        content_disposition_type=disposition,
    )

@router.post("/documents/{document_id}/retry", response_model=DocumentRead, status_code=202)
async def retry_document(
    document_id: str,
    request: Request,
    session: Session = Depends(get_session),
) -> DocumentRead:
    document = session.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    if not document.stored_path:
        raise HTTPException(status_code=400, detail="Document upload failed. Please upload the file again.")
    if document.status not in (DocumentStatus.processing_failed, DocumentStatus.failed):
        raise HTTPException(status_code=400, detail="Document is not eligible for retry.")

    document.status = DocumentStatus.pending
    document.failure_reason = None
    document.updated_at = datetime.utcnow()
    session.add(document)
    session.commit()
    session.refresh(document)

    asyncio.create_task(process_document(document.id))
    return _serialize_document(request, document)


@router.delete("/documents/{document_id}", status_code=204, response_class=Response)
async def delete_document(document_id: str, session: Session = Depends(get_session)) -> Response:
    document = session.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    stored_path = document.stored_path
    session.delete(document)
    session.commit()

    if stored_path:
        await storage.delete_upload(stored_path)

    return Response(status_code=204)


def _serialize_documents(request: Request, documents: Sequence[Document]) -> list[DocumentRead]:
    return [_serialize_document(request, doc) for doc in documents]


def _serialize_document(request: Request, document: Document) -> DocumentRead:
    download_url = None
    if document.stored_path:
        download_url = request.url_for("download_document", document_id=document.id)
    return DocumentRead(
        id=document.id,
        file_name=document.file_name,
        status=document.status,
        created_at=document.created_at,
        updated_at=document.updated_at,
        detections=document.detections,
        failure_reason=document.failure_reason,
        download_url=str(download_url) if download_url else None,
    )
