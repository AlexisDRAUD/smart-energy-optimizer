from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.config import settings
from app.db.init_db import initialize_database
from app.db.session import SessionLocal


@asynccontextmanager
async def lifespan(_: FastAPI):
    with SessionLocal() as db:
        initialize_database(db)
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}