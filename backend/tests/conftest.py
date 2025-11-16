from __future__ import annotations

import importlib
import os
from collections.abc import Generator
from pathlib import Path
import sys

TESTS_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = TESTS_DIR.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import pytest
from fastapi.testclient import TestClient


def _reload_modules() -> None:
    import app.config as config

    config.get_settings.cache_clear()
    importlib.reload(config)

    import app.services.storage as storage

    importlib.reload(storage)

    import app.database as database

    importlib.reload(database)
    database.init_db()

    import app.services.processor as processor

    importlib.reload(processor)

    import app.api as api

    importlib.reload(api)

    import app.main as main

    importlib.reload(main)


def _create_client() -> TestClient:
    from app.main import create_application

    app = create_application()

    async def _noop_process(document_id: str) -> None:  # noqa: ARG001
        return None

    import app.api as api

    api.process_document = _noop_process
    return TestClient(app)


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "test.db"
    storage_dir = tmp_path / "storage"
    monkeypatch.setenv("DI_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DI_STORAGE_DIR", str(storage_dir))

    _reload_modules()
    client = _create_client()
    with client:
        yield client
