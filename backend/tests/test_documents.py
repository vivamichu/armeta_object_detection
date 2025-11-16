from __future__ import annotations

from fastapi import UploadFile
from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session

from app import database
from app.models import Document, DocumentStatus


def test_healthcheck(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_upload_and_list_documents(client: TestClient) -> None:
    payload = b"%PDF-1.4 test pdf"
    files = [
        ("files", ("doc1.pdf", payload, "application/pdf")),
        ("files", ("doc2.pdf", payload, "application/pdf")),
    ]

    upload_response = client.post("/api/documents/upload", files=files)
    assert upload_response.status_code == 202
    body = upload_response.json()
    assert len(body["documents"]) == 2

    list_response = client.get("/api/documents")
    assert list_response.status_code == 200
    documents = list_response.json()["documents"]
    assert len(documents) == 2
    assert {doc["file_name"] for doc in documents} == {"doc1.pdf", "doc2.pdf"}


def test_upload_failure_sets_upload_failed_status(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.storage as storage

    async def _fail_save(document_id: str, upload: UploadFile) -> None:
        raise RuntimeError("disk full")

    monkeypatch.setattr(storage, "save_upload", _fail_save)

    payload = b"%PDF-1.4 test pdf"
    files = [("files", ("doc-error.pdf", payload, "application/pdf"))]

    response = client.post("/api/documents/upload", files=files)
    assert response.status_code == 202
    document = response.json()["documents"][0]
    assert document["status"] == "upload_failed"
    assert "disk full" in document["failure_reason"]


def test_retry_endpoint_resets_failed_document(client: TestClient) -> None:
    payload = b"%PDF-1.4 test pdf"
    files = [("files", ("doc.pdf", payload, "application/pdf"))]

    upload_response = client.post("/api/documents/upload", files=files)
    doc_id = upload_response.json()["documents"][0]["id"]

    with Session(database.engine) as session:
        document = session.get(Document, doc_id)
        assert document is not None
        document.status = DocumentStatus.processing_failed
        document.failure_reason = "ml boom"
        session.add(document)
        session.commit()

    retry_response = client.post(f"/api/documents/{doc_id}/retry")
    assert retry_response.status_code == 202
    retried = retry_response.json()
    assert retried["status"] == "pending"
    assert retried["failure_reason"] is None


def test_delete_document_removes_entry(client: TestClient) -> None:
    payload = b"%PDF-1.4 test pdf"
    files = [("files", ("doc.pdf", payload, "application/pdf"))]

    upload_response = client.post("/api/documents/upload", files=files)
    doc_id = upload_response.json()["documents"][0]["id"]

    delete_response = client.delete(f"/api/documents/{doc_id}")
    assert delete_response.status_code == 204

    list_response = client.get("/api/documents")
    assert list_response.status_code == 200
    assert list_response.json()["documents"] == []
