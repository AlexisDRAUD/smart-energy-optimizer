from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.api.v1.serializers import prediction_response
from app.core.contract import parse_utc, require_utc_range, utc_now
from app.db.models.prediction import Prediction
from app.db.models.site import Site
from app.schemas.contract import (
    ModelPerformanceResponse,
    ModelResponse,
    PredictionResponse,
    PredictionsResponse,
)
from app.services.prediction_service import (
    latest_prediction,
    model_metadata,
    performance_metrics,
)

router = APIRouter(prefix="/predictions", tags=["predictions"])
model_router = APIRouter(prefix="/model", tags=["model"])


def _site_or_404(db: DbSession, site_id: str) -> None:
    if db.get(Site, site_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")


@router.get("/latest", response_model=PredictionResponse)
def get_latest_prediction(
    site_id: str,
    _: CurrentUser,
    db: DbSession,
) -> dict[str, object]:
    _site_or_404(db, site_id)
    prediction = latest_prediction(db, site_id)
    if prediction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No prediction available for this site"
        )
    return prediction_response(prediction)


@router.get("", response_model=PredictionsResponse)
def prediction_history(
    site_id: str,
    _: CurrentUser,
    db: DbSession,
    start: str | None = None,
    end: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    _site_or_404(db, site_id)
    statement = select(Prediction).where(Prediction.site_id == site_id)
    if start is not None:
        statement = statement.where(Prediction.target_at >= parse_utc(start, "start"))
    if end is not None:
        statement = statement.where(Prediction.target_at < parse_utc(end, "end"))
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    predictions = list(
        db.scalars(statement.order_by(Prediction.target_at.desc()).offset(offset).limit(limit))
    )
    return {
        "items": [prediction_response(prediction) for prediction in predictions],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@model_router.get("", response_model=ModelResponse)
def get_model(_: CurrentUser) -> dict[str, object]:
    return model_metadata()


@model_router.get("/performance", response_model=ModelPerformanceResponse)
def get_model_performance(
    site_id: str,
    _: CurrentUser,
    db: DbSession,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, Any]:
    _site_or_404(db, site_id)
    now = utc_now()
    start_at, end_at = require_utc_range(
        start,
        end,
        default_start=now.replace(hour=0, minute=0, second=0, microsecond=0),
        default_end=now,
    )
    return performance_metrics(db, site_id, start_at, end_at)
