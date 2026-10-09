from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    """Naive UTC timestamp (SQLite stores DATETIME without a timezone)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class JobStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"

    FINISHED = (COMPLETED, COMPLETED_WITH_ERRORS, FAILED)


class CertStatus:
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(150))
    issued_by: Mapped[str] = mapped_column(String(150))
    issue_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default=JobStatus.PENDING, index=True)
    total: Mapped[int] = mapped_column(Integer, default=0)
    succeeded: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Certificate(Base):
    __tablename__ = "certificates"
    __table_args__ = (
        Index("ix_certificates_job_status", "job_id", "status"),
        UniqueConstraint("job_id", "position", name="uq_certificates_job_position"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)  # index of the recipient in the request
    recipient_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recipient_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=CertStatus.PENDING)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
