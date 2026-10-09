from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app import database, models  # noqa: F401  (models must be imported to register tables)
from app.config import settings
from app.routers.certificates import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.Base.metadata.create_all(bind=database.engine)
    Path(settings.storage_dir).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="Bulk Certificate Generator", version="1.0.0", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}
