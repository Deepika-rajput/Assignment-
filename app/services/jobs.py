import logging
import uuid
from datetime import date
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import database
from app.config import settings
from app.models import Certificate, CertStatus, Job, JobStatus
from app.schemas import JobCreate, RecipientIn
from app.services.certificate_pdf import generate_certificate_pdf

logger = logging.getLogger(__name__)


def _format_validation_error(exc: ValidationError) -> str:
    parts = [
        f"{'.'.join(str(p) for p in e['loc']) or 'recipient'}: {e['msg']}" for e in exc.errors()
    ]
    return "; ".join(parts)[:1000]


def _safe_str(raw, key: str) -> str | None:
    if isinstance(raw, dict) and isinstance(raw.get(key), str):
        return raw[key][:255]
    return None


def create_job(db: Session, payload: JobCreate) -> Job:
    """Persist the job + one row per recipient. Invalid recipients are stored as
    failed rows (with the reason) instead of rejecting the whole request."""
    job = Job(
        id=str(uuid.uuid4()),
        title=payload.title,
        issued_by=payload.issued_by,
        issue_date=payload.issue_date or date.today(),
        total=len(payload.recipients),
        succeeded=0,
        failed=0,
    )
    certs: list[Certificate] = []
    valid = 0
    for position, raw in enumerate(payload.recipients):
        cert = Certificate(id=str(uuid.uuid4()), job_id=job.id, position=position)
        try:
            recipient = RecipientIn.model_validate(raw)
            cert.recipient_name = recipient.name
            cert.recipient_email = recipient.email
            cert.status = CertStatus.PENDING
            valid += 1
        except ValidationError as exc:
            cert.recipient_name = _safe_str(raw, "name")
            cert.recipient_email = _safe_str(raw, "email")
            cert.status = CertStatus.FAILED
            cert.error = _format_validation_error(exc)
            job.failed += 1
        certs.append(cert)

    # nothing valid -> nothing to process, the job is finished right away
    job.status = JobStatus.PENDING if valid else JobStatus.FAILED
    db.add(job)
    db.flush()  # job row must exist before the certificates (FK)
    db.add_all(certs)
    db.commit()
    return job


def _final_status(job: Job) -> str:
    if job.failed == 0:
        return JobStatus.COMPLETED
    if job.succeeded == 0:
        return JobStatus.FAILED
    return JobStatus.COMPLETED_WITH_ERRORS


def process_job(job_id: str) -> None:
    """Background worker. Only touches certificates still 'pending', so it is safe
    to re-run for a job that was interrupted. One failing certificate is recorded
    and skipped; it never stops the rest of the job."""
    db = database.SessionLocal()
    try:
        job = db.get(Job, job_id)
        if job is None:
            return
        job.status = JobStatus.PROCESSING
        db.commit()

        out_dir = Path(settings.storage_dir) / job.id
        pending = db.scalars(
            select(Certificate)
            .where(Certificate.job_id == job.id, Certificate.status == CertStatus.PENDING)
            .order_by(Certificate.position)
        ).all()

        for cert in pending:
            path = out_dir / f"{cert.id}.pdf"
            try:
                generate_certificate_pdf(
                    path,
                    recipient_name=cert.recipient_name,
                    title=job.title,
                    issued_by=job.issued_by,
                    issue_date=job.issue_date,
                    certificate_id=cert.id,
                )
                cert.status = CertStatus.SUCCESS
                cert.file_path = str(path)
                job.succeeded += 1
            except Exception as exc:  # noqa: BLE001 - isolate every per-certificate failure
                logger.exception("Certificate %s failed", cert.id)
                cert.status = CertStatus.FAILED
                cert.error = f"Generation failed: {exc}"[:1000]
                job.failed += 1
            db.commit()  # commit per certificate so progress is visible while running

        job.status = _final_status(job)
        db.commit()
    except Exception as exc:  # noqa: BLE001 - e.g. DB went away mid-job
        logger.exception("Job %s crashed", job_id)
        db.rollback()
        job = db.get(Job, job_id)
        if job is not None:
            job.status = JobStatus.FAILED
            job.error = f"Unexpected error: {exc}"[:1000]
            db.commit()
    finally:
        db.close()
