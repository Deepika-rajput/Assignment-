# Bulk Certificate Generator

Backend API (FastAPI + SQLite) that takes a list of recipients in **one request**, generates a PDF
certificate for each from a single predefined template, tracks progress per job, and lets you
download the results (one by one or as a ZIP).

## Setup

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                    # optional, defaults already work
```

No database server needed: SQLite creates `certificates.db` in the project folder on first run.

Config (`.env`): `DATABASE_URL` (default `sqlite:///./certificates.db`), `STORAGE_DIR` (where PDFs are written), `MAX_RECIPIENTS_PER_JOB` (default 1000).
Tables are created automatically on startup.

## Run

```bash
uvicorn app.main:app --reload
```
Interactive docs: http://localhost:8000/docs

## Tests

```bash
pytest
```
Tests use a temporary SQLite file and temp storage, so they never touch your real data.

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/jobs` | Submit a bulk request -> `202` + job |
| GET | `/api/v1/jobs/{job_id}` | Status + progress |
| GET | `/api/v1/jobs/{job_id}/certificates?status=&limit=&offset=` | Per-recipient results (paginated) |
| GET | `/api/v1/certificates/{certificate_id}/download` | One PDF |
| GET | `/api/v1/jobs/{job_id}/download` | ZIP of all successful PDFs (finished jobs only) |

### Submit a request

```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Python Bootcamp 2026",
    "issued_by": "Acme Academy",
    "issue_date": "2026-10-01",
    "recipients": [
      {"name": "Asha Verma", "email": "asha@example.com"},
      {"name": "Rohan Mehta"},
      {"email": "no-name@example.com"}
    ]
  }'
```
Response (`202 Accepted`, also has a `Location` header):
```json
{"id": "5f0c...", "status": "pending", "total": 3, "succeeded": 0, "failed": 1,
 "progress_percent": 33.3, "download_url": null, "...": "..."}
```

### Check progress

```bash
curl http://localhost:8000/api/v1/jobs/<job_id>
curl "http://localhost:8000/api/v1/jobs/<job_id>/certificates?status=failed"   # why did some fail?
```
Job `status`: `pending` -> `processing` -> `completed` | `completed_with_errors` | `failed` (nothing succeeded).

### Retrieve certificates

```bash
curl -OJ http://localhost:8000/api/v1/certificates/<certificate_id>/download   # single PDF
curl -OJ http://localhost:8000/api/v1/jobs/<job_id>/download                   # ZIP of everything
```
Each item in the certificates list carries its own `download_url`.

## Design decisions

- **Background processing (FastAPI `BackgroundTasks`)** instead of synchronous generation. A request can hold
  up to 1000 recipients; generating inline would hold the HTTP connection open and risk timeouts. The API
  validates + stores everything, returns `202` immediately, and the client polls the job. Chosen over
  Celery/Redis because it needs no extra infrastructure for this scope.
  *Trade-off:* work lives in the API process, so a restart mid-job loses the in-flight run. `process_job` only
  touches certificates still `pending`, so it is idempotent and safe to re-queue; in production I'd move it to
  a real queue (Celery/RQ) with a retry endpoint.
- **Validation is two-level.** The envelope (title, issuer, 1..1000 recipients, date) is validated strictly
  -> `422`. Each *recipient* is validated individually: an invalid one is stored as a `failed` certificate
  with the reason and the rest of the job proceeds. One bad row never rejects the whole batch.
- **Failure isolation.** Each certificate is generated in its own try/except and committed individually.
  A failure is recorded on that certificate (`status=failed`, `error=...`) and the loop continues.
  An unexpected crash of the whole job marks it `failed` with an error message.
- **Progress** is stored as counters on the job (`succeeded`, `failed`, `total`) and committed after every
  certificate, so `GET /jobs/{id}` shows live progress. `progress_percent` is derived.
- **PDF generation:** ReportLab, one hard-coded landscape A4 template. Files are written to a temp name and
  renamed, so no half-written PDFs. Files live on disk under `STORAGE_DIR/<job_id>/<certificate_id>.pdf`;
  only the path is in the database. UUID filenames mean user input never touches the filesystem path.
- **Data model:** `jobs` (1) -> `certificates` (N, indexed on `(job_id, status)`, unique `(job_id, position)`).
  Statuses are plain strings for portability.
- **SQLite** keeps setup to zero (no server, one file). The API thread and the background worker both write,
  so the connection enables `PRAGMA journal_mode=WAL` (readers don't block writes), a 30s busy timeout, and
  `PRAGMA foreign_keys=ON` (SQLite ignores FKs by default). Writers are serialized by SQLite, which is fine at
  this scale because the worker commits one small row at a time.
- **Certificate listing is paginated** (max 500 per page) since a job can be large.

## Known limitations / next steps

- The built-in PDF font only covers Latin-1 (cp1252); names with other scripts are rejected per-recipient
  with a clear error. Supporting them = register a TTF (e.g. Noto) with ReportLab.
- No auth, rate limiting, or email delivery. No Alembic migrations (`create_all` on startup).
- Local disk storage; swap for S3/object storage for multi-instance deployments.
- SQLite allows one writer at a time and one file on one machine. For many concurrent jobs or multiple app
  instances, point `DATABASE_URL` at Postgres/MySQL (install the driver) - the models use portable types only.
