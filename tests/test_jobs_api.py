import io
import zipfile
from datetime import date

from app import database
from app.models import Job
from app.services import jobs as job_service
from app.services.certificate_pdf import generate_certificate_pdf as real_generate


def submit(client, payload):
    """POST a job, then re-fetch it: the 202 body is the job as created (pending);
    the background task has finished by the time post() returns in TestClient."""
    created = client.post("/api/v1/jobs", json=payload)
    assert created.status_code == 202
    return client.get(f"/api/v1/jobs/{created.json()['id']}").json()


def _certs(client, job_id, **params):
    r = client.get(f"/api/v1/jobs/{job_id}/certificates", params=params)
    assert r.status_code == 200
    return r.json()


# ---------- creating a job ----------
def test_create_job_returns_202_with_job_info(client, payload):
    r = client.post("/api/v1/jobs", json=payload)
    assert r.status_code == 202
    body = r.json()
    assert body["total"] == 3
    assert body["id"]
    assert r.headers["location"] == f"/api/v1/jobs/{body['id']}"


# ---------- input validation ----------
def test_envelope_validation_rejects_bad_requests(client, payload):
    assert client.post("/api/v1/jobs", json={**payload, "title": ""}).status_code == 422
    assert client.post("/api/v1/jobs", json={**payload, "issued_by": ""}).status_code == 422
    assert client.post("/api/v1/jobs", json={**payload, "recipients": []}).status_code == 422
    assert client.post("/api/v1/jobs", json={**payload, "issue_date": "nope"}).status_code == 422
    too_many = [{"name": "x"}] * 1001
    assert client.post("/api/v1/jobs", json={**payload, "recipients": too_many}).status_code == 422


def test_invalid_recipients_are_failed_individually(client, payload):
    payload["recipients"] = [
        {"name": "Good Person", "email": "good@example.com"},
        {"email": "noname@example.com"},  # missing name
        {"name": "Bad Email", "email": "not-an-email"},
        {"name": "   "},  # blank after strip
        {"name": "देवनागरी"},  # cannot be rendered by the PDF font
        "just a string",
    ]
    job = submit(client, payload)
    assert job["status"] == "completed_with_errors"
    assert job["succeeded"] == 1
    assert job["failed"] == 5

    failed = _certs(client, job["id"], status="failed")
    assert failed["total"] == 5
    assert all(item["error"] for item in failed["items"])
    assert any("email" in item["error"] for item in failed["items"])


def test_all_recipients_invalid_marks_job_failed(client, payload):
    payload["recipients"] = [{"name": ""}, {"foo": "bar"}]
    job = submit(client, payload)
    assert job["status"] == "failed"
    assert job["failed"] == 2
    assert job["download_url"] is None


# ---------- certificate generation ----------
def test_job_generates_a_pdf_per_valid_recipient(client, payload, tmp_path):
    job = submit(client, payload)
    assert job["status"] == "completed"
    assert job["succeeded"] == 3 and job["failed"] == 0

    page = _certs(client, job["id"], status="success")
    assert page["total"] == 3
    for item in page["items"]:
        r = client.get(item["download_url"])
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.content.startswith(b"%PDF")
    stored = list((tmp_path / "storage" / job["id"]).glob("*.pdf"))
    assert len(stored) == 3


# ---------- status / progress ----------
def test_job_status_and_progress_after_completion(client, payload):
    job = submit(client, payload)
    r = client.get(f"/api/v1/jobs/{job['id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["progress_percent"] == 100.0
    assert body["download_url"] == f"/api/v1/jobs/{job['id']}/download"


def test_job_progress_while_processing(client):
    with database.SessionLocal() as db:
        db.add(
            Job(
                id="job-in-flight",
                title="T",
                issued_by="I",
                issue_date=date(2026, 10, 1),
                status="processing",
                total=4,
                succeeded=1,
                failed=1,
            )
        )
        db.commit()
    body = client.get("/api/v1/jobs/job-in-flight").json()
    assert body["status"] == "processing"
    assert body["progress_percent"] == 50.0
    assert body["download_url"] is None


def test_unknown_job_is_404(client):
    assert client.get("/api/v1/jobs/does-not-exist").status_code == 404
    assert client.get("/api/v1/jobs/does-not-exist/certificates").status_code == 404


# ---------- one certificate failing ----------
def test_single_generation_failure_does_not_stop_the_job(client, payload, monkeypatch):
    def flaky(path, **kwargs):
        if kwargs["recipient_name"] == "Rohan Mehta":
            raise RuntimeError("renderer exploded")
        return real_generate(path, **kwargs)

    monkeypatch.setattr(job_service, "generate_certificate_pdf", flaky)

    job = submit(client, payload)
    assert job["status"] == "completed_with_errors"
    assert job["succeeded"] == 2
    assert job["failed"] == 1

    failed = _certs(client, job["id"], status="failed")["items"]
    assert len(failed) == 1
    assert failed[0]["recipient_name"] == "Rohan Mehta"
    assert "renderer exploded" in failed[0]["error"]
    assert failed[0]["download_url"] is None
    assert client.get(f"/api/v1/certificates/{failed[0]['id']}/download").status_code == 404
    assert _certs(client, job["id"], status="success")["total"] == 2


# ---------- retrieving certificates ----------
def test_list_certificates_pagination(client, payload):
    payload["recipients"] = [{"name": f"Person {i}"} for i in range(5)]
    job = submit(client, payload)
    page = _certs(client, job["id"], limit=2, offset=2)
    assert page["total"] == 5
    assert [i["position"] for i in page["items"]] == [2, 3]
    assert client.get(f"/api/v1/jobs/{job['id']}/certificates?status=bogus").status_code == 422


def test_download_zip_contains_all_successful_certificates(client, payload):
    job = submit(client, payload)
    r = client.get(job["download_url"])
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        names = zf.namelist()
        assert len(names) == 3
        assert names[0].startswith("0001-asha-verma")
        assert zf.read(names[0]).startswith(b"%PDF")


def test_download_zip_before_finish_is_409(client):
    with database.SessionLocal() as db:
        db.add(Job(id="busy", title="T", issued_by="I", issue_date=date(2026, 10, 1),
                   status="processing", total=2))
        db.commit()
    assert client.get("/api/v1/jobs/busy/download").status_code == 409


def test_download_unknown_certificate_is_404(client):
    assert client.get("/api/v1/certificates/nope/download").status_code == 404
