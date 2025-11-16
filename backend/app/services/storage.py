from __future__ import annotations

import asyncio
from pathlib import Path

import aiofiles
from fastapi import UploadFile

from ..config import get_settings

settings = get_settings()


def document_path(document_id: str) -> Path:
    return settings.storage_dir / f"{document_id}.pdf"


async def save_upload(document_id: str, upload: UploadFile) -> Path:
    destination = document_path(document_id)
    destination.parent.mkdir(parents=True, exist_ok=True)

    async with aiofiles.open(destination, "wb") as out_file:
        while chunk := await upload.read(1024 * 1024):
            await out_file.write(chunk)

    await upload.close()
    return destination


async def delete_upload(path: str | Path | None) -> None:
    if not path:
        return

    destination = Path(path)
    try:
        await asyncio.to_thread(destination.unlink, missing_ok=True)
    except OSError:
        # File may already be gone or in use; swallow errors to keep API idempotent.
        return
