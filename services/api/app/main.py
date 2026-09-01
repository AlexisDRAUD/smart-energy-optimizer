from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.router import api_router
from app.config import settings
from app.db.init_db import initialize_database
from app.db.session import SessionLocal, verify_database_connection


@asynccontextmanager
async def lifespan(_: FastAPI):
    verify_database_connection()
    with SessionLocal() as db:
        initialize_database(db)
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", response_class=HTMLResponse, tags=["root"])
def index() -> HTMLResponse:
    """Index page to verify the API is running."""
    html = """
    <html>
      <head><title>Smart Energy Optimizer</title></head>
      <body>
        <h1>Smart Energy Optimizer API</h1>
        <p>Le serveur fonctionne correctement.</p>
      </body>
    </html>
    """
    return HTMLResponse(content=html, status_code=200)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    try:
        verify_database_connection()
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from error
    return {"status": "ok", "database": "available"}