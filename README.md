# Digital Inspector

## Running the app

```bash
docker compose up --build
```

- Backend API: <http://localhost:8000/api>
- Frontend UI: <http://localhost:5173>


Shut everything down with `CTRL+C`, then `docker compose down` (add `-v` to wipe the volume).


## Architecture at a glance
| Layer | Technology | Notes |
| --- | --- | --- |
| Frontend | React 18, TypeScript, Vite, pdf.js | Upload UI, history table, multi-page PDF viewer with bounding boxes. |
| Backend | FastAPI, SQLModel, Uvicorn, aiofiles | REST API, async uploads, background processing tasks. |
| Database | SQLite (via SQLModel) | Default local store; easy to swap for Postgres/MySQL via `DI_DATABASE_URL`. |
| Storage | Local filesystem (`storage/` or Docker volume) | Persists uploaded PDFs and detection output. |
| ML Client | pdf2image + Ultralytics YOLOv8 | Converts PDFs to page images and runs the bundled `best.pt` (classes: `qr`, `signature`, `stamp`, `stamp_q`). |
| Containerization | Dockerfiles + `docker-compose.yml` | One command to run both services with a shared volume. |

## Key features
- **Multi-file uploads** with drag-and-drop UI, batching, and per-file status badges.
- **Retry vs. upload failure differentiation** so operators know when to re-upload vs. reprocess.
- **Interactive PDF viewer** that renders all pages and overlays detected bounding boxes.
- **Recent history table** with Preview, Download, Remove, and Retry controls alongside failure reasons.
- **Optimized polling loop** that hashes document payloads to avoid unnecessary re-renders while keeping statuses fresh.
- **Drop-in YOLO weights**: swap the bundled `best.pt` file (classes: `qr`, `signature`, `stamp`, `stamp_q`) via `DI_MODEL_PATH` to retarget detections.
- **Typed backend models & schemas** shared between persistence and API responses via SQLModel & Pydantic.

## Repository layout
```
backend/
  app/
    api.py          # REST endpoints
    models.py       # SQLModel entities & status enum
    schemas.py      # Pydantic response payloads
    services/       # Storage, ML client, processor workers
    main.py         # FastAPI factory + router wiring
  tests/            # Pytest suite and fixtures
  requirements.txt
frontend/
  src/
    App.tsx        # Top-level UI & data orchestration
    components/    # Upload panel, PDF viewer, gallery
    styles.css     # Global styling
  package.json
experiments/        # Research notebooks/scripts (not part of runtime stack)
Dockerfile(s), docker-compose.yml, README.md
```

## Configuration
All backend settings can be overridden via environment variables prefixed with `DI_` (see `backend/.env.example`). Key options:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DI_APP_NAME` | `Digital Inspector API` | FastAPI title. |
| `DI_API_PREFIX` | `/api` | Router prefix. |
| `DI_DATABASE_URL` | `sqlite:///./app.db` | SQLModel connection string. Use Postgres/MySQL URI for production. |
| `DI_STORAGE_DIR` | `storage` | Filesystem path for uploaded PDFs. Mounted to `/data/storage` inside Docker. |
| `DI_LOG_LEVEL` | `INFO` | Log verbosity across services. |
| `DI_MODEL_PATH` | `best.pt` | Absolute or relative path to the Ultralytics weights. Swap this to change models. |
| `DI_MODEL_CONFIDENCE` | `0.35` | Minimum confidence threshold passed to YOLO. |
| `DI_PDF_DPI` | `200` | DPI for pdf2image when rasterizing each page. |

Frontend configuration is minimal—set `VITE_API_BASE_URL` in `frontend/.env` when the API lives elsewhere.

## API surface
All endpoints live under `/api` by default.

| Method & Path | Description |
| --- | --- |
| `POST /documents/upload` | Accepts one or more PDFs (`multipart/form-data`). Creates pending records and kicks off processing. |
| `GET /documents` | Lists documents ordered by creation time (newest first). |
| `GET /documents/{id}` | Fetches a single document with detections and status. |
| `GET /documents/{id}/file?download=1` | Streams the stored PDF inline or as an attachment. |
| `POST /documents/{id}/retry` | Resets a failed document (processing errors only) and restarts processing. |
| `DELETE /documents/{id}` | Removes a document and its stored file. |

Statuses include `pending`, `processing`, `succeeded`, `processing_failed`, and `upload_failed`. The frontend exposes retry buttons for processing failures and instructs users to re-upload when storage fails.

## Persistence & storage
- **Database**: SQLModel + SQLite by default (`backend/app/database.py`). Tables auto-migrate on startup.
- **Storage**: PDFs are written to `DI_STORAGE_DIR` using `aiofiles`. The Docker stack mounts a named volume so restarts do not destroy data.
- **Page images**: `pdf2image` renders each PDF page into a temporary PNG before detection. These files live in a temp directory that is deleted after inference completes.
- **Experiments**: Research scripts and sample PDFs live under `experiments/` for benchmarking and demos; they are not loaded at runtime.
