from datetime import date, datetime
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    computed_field,
    field_validator,
)

from app.config import settings
from app.models import CertStatus, JobStatus


# ---------- requests ----------
class RecipientIn(BaseModel):
    """Validated per recipient so one bad row never rejects the whole request."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    name: str = Field(min_length=1, max_length=80)
    email: EmailStr | None = None

    @field_validator("name")
    @classmethod
    def name_must_be_printable_and_renderable(cls, v: str) -> str:
        if any(ord(ch) < 32 for ch in v):
            raise ValueError("name contains control characters")
        try:
            v.encode("cp1252")  # the built-in PDF font only covers Latin-1/cp1252
        except UnicodeEncodeError:
            raise ValueError("name contains characters the certificate font cannot render")
        return v


class JobCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=120, description="Course / event name")
    issued_by: str = Field(min_length=1, max_length=100)
    issue_date: date | None = None  # defaults to today
    # Items are validated individually (see RecipientIn) -> partial success is possible.
    recipients: list[Any] = Field(min_length=1, max_length=settings.max_recipients_per_job)


# ---------- responses ----------
class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    issued_by: str
    issue_date: date
    status: str
    total: int
    succeeded: int
    failed: int
    error: str | None = None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def progress_percent(self) -> float:
        if not self.total:
            return 100.0
        return round((self.succeeded + self.failed) / self.total * 100, 1)

    @computed_field
    @property
    def download_url(self) -> str | None:
        if self.status in JobStatus.FINISHED and self.succeeded > 0:
            return f"/api/v1/jobs/{self.id}/download"
        return None


class CertificateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    position: int
    recipient_name: str | None
    recipient_email: str | None
    status: str
    error: str | None = None

    @computed_field
    @property
    def download_url(self) -> str | None:
        if self.status == CertStatus.SUCCESS:
            return f"/api/v1/certificates/{self.id}/download"
        return None


class CertificatePage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[CertificateOut]
