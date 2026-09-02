import asyncio
from contextlib import asynccontextmanager, suppress
from logging import getLogger

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.config import settings
from app.db.session import SessionLocal, verify_database_connection
from app.schemas.contract import ErrorResponse
from app.services.prediction_service import model_metadata, refresh_stored_predictions

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

    stop_event = asyncio.Event()
    refresh_task = asyncio.create_task(refresh_predictions_periodically(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        refresh_task.cancel()
        with suppress(asyncio.CancelledError):
            await refresh_task


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Authoritative v1 API contract for Smart Energy Optimizer.",
    lifespan=lifespan,
)
app.include_router(
    api_router,
    prefix=settings.api_v1_prefix,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)


def _error_code(status_code: int) -> str:
    return {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        422: "validation_error",
        503: "service_unavailable",
    }.get(status_code, "http_error")


@app.exception_handler(StarletteHTTPException)
@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, error: StarletteHTTPException) -> JSONResponse:
    message = error.detail if isinstance(error.detail, str) else "Request failed"
    return JSONResponse(
        status_code=error.status_code,
        content={"error": {"code": _error_code(error.status_code), "message": message}},
        headers=error.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, error: RequestValidationError) -> JSONResponse:
    first_error = error.errors()[0] if error.errors() else {}
    message = str(first_error.get("msg", "Invalid request"))
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"error": {"code": "validation_error", "message": message}},
    )


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
    return {
        "status": "ok",
        "database": "available",
        "model_version": model_metadata()["model_version"],
    }
