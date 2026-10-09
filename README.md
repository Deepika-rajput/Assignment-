# Bulk Certificate Generator

Backend API (FastAPI + SQLite) that takes a list of recipients in **one request**, generates a PDF
certificate for each from a single predefined template, tracks progress per job, and lets you
download the results (one by one or as a ZIP).

output example-[0002-rahul-verma.pdf](https://github.com/user-attachments/files/33240787/0002-rahul-verma.pdf)


## Setup%PDF-1.4
%���� ReportLab Generated PDF document (opensource)
1 0 obj
<<
/F1 2 0 R /F2 3 0 R /F3 4 0 R
>>
endobj
2 0 obj
<<
/BaseFont /Helvetica /Encoding /WinAnsiEncoding /Name /F1 /Subtype /Type1 /Type /Font
>>
endobj
3 0 obj
<<
/BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding /Name /F2 /Subtype /Type1 /Type /Font
>>
endobj
4 0 obj
<<
/BaseFont /Helvetica-Oblique /Encoding /WinAnsiEncoding /Name /F3 /Subtype /Type1 /Type /Font
>>
endobj
5 0 obj
<<
/Contents 9 0 R /MediaBox [ 0 0 841.8898 595.2756 ] /Parent 8 0 R /Resources <<
/Font 1 0 R /ProcSet [ /PDF /Text /ImageB /ImageC /ImageI ]
>> /Rotate 0 /Trans <<

>> 
  /Type /Page
>>
endobj
6 0 obj
<<
/PageMode /UseNone /Pages 8 0 R /Type /Catalog
>>
endobj
7 0 obj
<<
/Author (Amazon Web Services) /CreationDate (D:20261009134059+05'00') /Creator (anonymous) /Keywords () /ModDate (D:20261009134059+05'00') /Producer (ReportLab PDF Library - \(opensource\)) 
  /Subject (unspecified) /Title (Certificate - Rahul Verma) /Trapped /False
>>
endobj
8 0 obj
<<
/Count 1 /Kids [ 5 0 R ] /Type /Pages
>>
endobj
9 0 obj
<<
/Filter [ /ASCII85Decode /FlateDecode ] /Length 621
>>
stream
Gatn"?a#YI(rl%?'[NVEXL9d!Bm2L[2RDK.:,_+B#$)]JL&n0>TABY@30,k8;/#`kQJ_R%I9lsB:GH+\$@!6Eohn$diZ(9?M>/-M3+1H\@5XEMA>K:$Y^aIND'8@+3.Osm+tK$8ej)gG-rLtC__r(DPYh#tMLJ6mb:.oB1`q@D-A'`q:!,+MfAs])F8;U@1KIUK_\#sp0jebVeT*O>`J^(=59YJ5W":5=[U;GFLjKtQImd'D0AQ12&kr<8$)M5h$p@"Y!O?$@^4,fq^PGtWpGZJHLd?s'f<g4Z1;f)?BLbb/03\.ue];"E(&80l53ZqbHLl@lPidjGehCs:a2u`?9sR!Lpu%Sjq$Vid!&J*dLbgRY+-AhmIJI(?48a$":rlVsQ]iH5ga=]-A!X[6c&ZF]6<70[9@p`19ubPAFOErVs2>o$9VadLNB8kAggXU@`uQ4i,jU>jW"6&A/RZmdlVaM?N$MO30l"?o3]@5O=D(p1\d$)Es$'a:4O3EBg!NgS*o.=jBo6&YI&dd&F=FZ$q,2I(0<qNq<SsRtmQ[sD(YPi`7)ZJ+krr<4*thji?7Ap!;^cR/UiJI-c:/JHGW89#P"r+?3mY_s:H?0<"i5C+)AKL~>endstream
endobj
xref
0 10
0000000000 65535 f 
0000000061 00000 n 
0000000112 00000 n 
0000000219 00000 n 
0000000331 00000 n 
0000000446 00000 n 
0000000649 00000 n 
0000000717 00000 n 
0000001005 00000 n 
0000001064 00000 n 
trailer
<<
/ID 
[<23899a02f3304e1bb3456fd0cb2f52ac><23899a02f3304e1bb3456fd0cb2f52ac>]
% ReportLab generated PDF document -- digest (opensource)

/Info 7 0 R
/Root 6 0 R
/Size 10
>>
startxref
1775
%%EOF


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

