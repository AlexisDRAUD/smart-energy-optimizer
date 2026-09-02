from __future__ import annotations

from datetime import UTC, datetime, timedelta
from math import sqrt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.contract import as_utc
from app.models.prediction import Prediction
from app.models.reading import Reading
from app.models.site import Site

PREDICTION_HORIZON_MINUTES = 120


def model_metadata() -> dict[str, object]:
    """Describe the startup-loaded local fallback without requiring MLflow."""
    return {
        "model_name": settings.local_model_name,
        "model_version": settings.local_model_version,
        "trained_at": None,
        "horizon_minutes": PREDICTION_HORIZON_MINUTES,
        "test_metrics": {"mae": None, "rmse": None, "mape_percent": None},
        "availability": "local_fallback",
        "mlflow_available": False,
    }


def score_due_predictions(db: Session, scored_at: datetime) -> int:
    """Attach real values to due forecasts once the ETL has written them."""
    scored = 0
    due_predictions = list(
        db.scalars(
            select(Prediction).where(
                Prediction.actual_kwh.is_(None),
                Prediction.target_at <= scored_at,
            )
        )
    )
    for prediction in due_predictions:
        actual_kwh = db.scalar(
            select(Reading.consumption_kwh).where(
                Reading.site_id == prediction.site_id,
                Reading.measured_at == prediction.target_at,
            )
        )
        if actual_kwh is None:
            continue
        prediction.actual_kwh = actual_kwh
        prediction.scored_at = scored_at
        scored += 1
    return scored


def refresh_stored_predictions(db: Session, now: datetime | None = None) -> int:
    """Persist one 120-minute forecast for the latest available reading of each site."""
    predicted_at = as_utc(now or datetime.now(UTC)).replace(second=0, microsecond=0)
    score_due_predictions(db, predicted_at)
    created = 0
    for site in db.scalars(select(Site).where(Site.status == "active")):
        latest = db.scalar(
            select(Reading)
            .where(Reading.site_id == site.site_id)
            .order_by(Reading.measured_at.desc())
            .limit(1)
        )
        if latest is None:
            continue

        target_at = as_utc(latest.measured_at) + timedelta(minutes=PREDICTION_HORIZON_MINUTES)
        existing = db.scalar(
            select(Prediction.id).where(
                Prediction.site_id == site.site_id,
                Prediction.target_at == target_at,
                Prediction.model_version == settings.local_model_version,
                Prediction.horizon_minutes == PREDICTION_HORIZON_MINUTES,
            )
        )
        if existing is not None:
            continue

        recent = list(
            db.scalars(
                select(Reading.consumption_kwh)
                .where(Reading.site_id == site.site_id, Reading.consumption_kwh.is_not(None))
                .order_by(Reading.measured_at.desc())
                .limit(24)
            )
        )
        if not recent:
            continue
        db.add(
            Prediction(
                site_id=site.site_id,
                predicted_at=predicted_at,
                target_at=target_at,
                horizon_minutes=PREDICTION_HORIZON_MINUTES,
                model_name=settings.local_model_name,
                model_version=settings.local_model_version,
                predicted_kwh=round(sum(recent) / len(recent), 3),
                actual_kwh=None,
                scored_at=None,
            )
        )
        created += 1
    db.commit()
    return created


def latest_prediction(db: Session, site_id: str) -> Prediction | None:
    return db.scalar(
        select(Prediction)
        .where(Prediction.site_id == site_id)
        .order_by(Prediction.predicted_at.desc(), Prediction.id.desc())
        .limit(1)
    )


def metric(values: list[tuple[float, float]]) -> dict[str, float | None]:
    if not values:
        return {"mae": None, "rmse": None, "mape_percent": None}
    errors = [abs(predicted - actual) for predicted, actual in values]
    return {
        "mae": round(sum(errors) / len(errors), 3),
        "rmse": round(sqrt(sum(error**2 for error in errors) / len(errors)), 3),
        "mape_percent": round(
            sum(
                error / abs(actual) * 100
                for error, (_, actual) in zip(errors, values, strict=True)
                if actual
            )
            / sum(1 for _, actual in values if actual),
            3,
        )
        if any(actual for _, actual in values)
        else None,
    }


def performance_metrics(
    db: Session,
    site_id: str,
    start_at: datetime,
    end_at: datetime,
) -> dict[str, object]:
    scored = list(
        db.scalars(
            select(Prediction)
            .where(
                Prediction.site_id == site_id,
                Prediction.actual_kwh.is_not(None),
                Prediction.target_at >= start_at,
                Prediction.target_at < end_at,
            )
            .order_by(Prediction.target_at)
        )
    )
    model_values: list[tuple[float, float]] = []
    persistence_values: list[tuple[float, float]] = []
    linear_values: list[tuple[float, float]] = []
    for prediction in scored:
        actual = prediction.actual_kwh
        if actual is None:
            continue
        model_values.append((prediction.predicted_kwh, actual))
        baseline_time = as_utc(prediction.target_at) - timedelta(minutes=prediction.horizon_minutes)
        latest = db.scalar(
            select(Reading)
            .where(
                Reading.site_id == prediction.site_id,
                Reading.measured_at <= baseline_time,
                Reading.consumption_kwh.is_not(None),
            )
            .order_by(Reading.measured_at.desc())
            .limit(1)
        )
        if latest is None or latest.consumption_kwh is None:
            continue
        persistence_values.append((latest.consumption_kwh, actual))
        prior = db.scalar(
            select(Reading)
            .where(
                Reading.site_id == prediction.site_id,
                Reading.measured_at < latest.measured_at,
                Reading.consumption_kwh.is_not(None),
            )
            .order_by(Reading.measured_at.desc())
            .limit(1)
        )
        if prior is None or prior.consumption_kwh is None:
            continue
        linear_values.append(
            (
                latest.consumption_kwh
                + (latest.consumption_kwh - prior.consumption_kwh) * prediction.horizon_minutes,
                actual,
            )
        )
    return {
        "sample_size": len(model_values),
        "model": metric(model_values),
        "persistence_baseline": metric(persistence_values),
        "linear_baseline": metric(linear_values),
    }
