from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = None
SessionLocal = None


def init_engine(url: str) -> None:
    """(Re)create the engine + session factory. Tests call this with a temp DB file."""
    global engine, SessionLocal
    if engine is not None:
        engine.dispose()
    kwargs: dict = {}
    if url.startswith("sqlite"):
        # the API thread and the background worker thread both use the DB
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
    engine = create_engine(url, **kwargs)

    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")  # enforce FK + ON DELETE CASCADE
            cur.execute("PRAGMA journal_mode=WAL")  # readers don't block the worker's writes
            cur.close()

    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


init_engine(settings.database_url)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
