import io
import re
import zipfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Certificate, CertStatus, Job, JobStatus
from app.schemas import CertificatePage, JobCreate, JobOut
from app.services import jobs as job_service

router = APIRouter(prefix="/api/v1")


def _slug(name: str | None) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", name or "").strip("-").lower() or "certificate"


def _get_job_or_404(db: Session, job_id: str) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/jobs", response_model=JobOut, status_code=202)
def create_job(
    payload: JobCreate,
    background_tasks: BackgroundTasks,
    response: Response,
    db: Session = Depends(get_db),
):
    """Submit many recipients in one request. Returns immediately (202); poll the job."""
    job = job_service.create_job(db, payload)
    if job.status == JobStatus.PENDING:
        background_tasks.add_task(job_service.process_job, job.id)
    response.headers["Location"] = f"/api/v1/jobs/{job.id}"
    return job


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_db)):
    return _get_job_or_404(db, job_id)


@router.get("/jobs/{job_id}/certificates", response_model=CertificatePage)
def list_certificates(
    job_id: str,
    status: str | None = Query(None, pattern="^(pending|success|failed)$"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    _get_job_or_404(db, job_id)
    query = select(Certificate).where(Certificate.job_id == job_id)
    if status:
        query = query.where(Certificate.status == status)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = db.scalars(query.order_by(Certificate.position).limit(limit).offset(offset)).all()
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@router.get("/jobs/{job_id}/download")
def download_job_zip(job_id: str, db: Session = Depends(get_db)):
    """All successfully generated certificates of a finished job as one ZIP."""
    job = _get_job_or_404(db, job_id)
    if job.status not in JobStatus.FINISHED:
        raise HTTPException(status_code=409, detail="Job is not finished yet")
    certs = db.scalars(
        select(Certificate)
        .where(Certificate.job_id == job_id, Certificate.status == CertStatus.SUCCESS)
        .order_by(Certificate.position)
    ).all()
    if not certs:
        raise HTTPException(status_code=404, detail="No certificates were generated for this job")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for cert in certs:
            path = Path(cert.file_path or "")
            if path.is_file():
                zf.write(path, arcname=f"{cert.position + 1:04d}-{_slug(cert.recipient_name)}.pdf")
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="certificates-{job.id}.zip"'},
    )


@router.get("/certificates/{certificate_id}/download")
def download_certificate(certificate_id: str, db: Session = Depends(get_db)):
    cert = db.get(Certificate, certificate_id)
    if cert is None:
        raise HTTPException(status_code=404, detail="Certificate not found")
    if cert.status != CertStatus.SUCCESS or not cert.file_path or not Path(cert.file_path).is_file():
        raise HTTPException(status_code=404, detail="Certificate file is not available")
    return FileResponse(
        cert.file_path,
        media_type="application/pdf",
        filename=f"{_slug(cert.recipient_name)}-certificate.pdf",
    )
