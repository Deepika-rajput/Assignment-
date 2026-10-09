import pytest
from fastapi.testclient import TestClient

from app import database
from app.config import settings


@pytest.fixture
def client(tmp_path, monkeypatch):
    """App wired to a throwaway SQLite DB + temp storage.
    TestClient runs BackgroundTasks before .post() returns, so jobs are finished
    by the time a test inspects them."""
    database.init_engine(f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path / "storage"))
    from app.main import app

    with TestClient(app) as c:
        yield c
    database.engine.dispose()


@pytest.fixture
def payload():
    return {
        "title": "Python Bootcamp 2026",
        "issued_by": "Acme Academy",
        "issue_date": "2026-10-01",
        "recipients": [
            {"name": "Asha Verma", "email": "asha@example.com"},
            {"name": "Rohan Mehta", "email": "rohan@example.com"},
            {"name": "Meera Iyer"},
        ],
    }
