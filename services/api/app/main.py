import asyncio
from contextlib import asynccontextmanager, suppress
from logging import getLogger

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.router import api_router
from app.config import settings
from app.db.init_db import initialize_database
from app.db.session import SessionLocal, verify_database_connection
from app.services.prediction_service import refresh_stored_predictions

logger = getLogger(__name__)


def refresh_predictions() -> None:
    with SessionLocal() as db:
        refresh_stored_predictions(db)


async def refresh_predictions_periodically(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await asyncio.to_thread(refresh_predictions)
        except SQLAlchemyError:
            logger.exception("Unable to refresh stored predictions")

        with suppress(asyncio.TimeoutError):
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=settings.prediction_refresh_interval_seconds,
            )


@asynccontextmanager
async def lifespan(_: FastAPI):
    verify_database_connection()
    with SessionLocal() as db:
        initialize_database(db)

    stop_event = asyncio.Event()
    refresh_task = asyncio.create_task(refresh_predictions_periodically(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        refresh_task.cancel()
        with suppress(asyncio.CancelledError):
            await refresh_task


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
