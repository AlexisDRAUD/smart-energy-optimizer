from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import sqrt

import pandas as pd
from seo_features import build_feature_frame
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.contract import as_utc
from app.db.models.prediction import Prediction
from app.db.models.reading import Reading
from app.db.models.site import Site

try:
    import mlflow
    from mlflow import MlflowClient
    from mlflow.exceptions import MlflowException
except ImportError:  # pragma: no cover - optional in dev/test environments
    mlflow = None
    MlflowClient = None
    MlflowException = Exception

PREDICTION_HORIZON_MINUTES = 120
MODEL_INPUT_WINDOW_MINUTES = 240


@dataclass
class SiteModel:
    model_name: str
    model_version: str
    model: object


_MODEL_CACHE: dict[str, SiteModel] = {}
_MLFLOW_CLIENT: MlflowClient | None = None


def _mlflow_enabled() -> bool:
    return bool(settings.mlflow_tracking_uri and mlflow is not None and MlflowClient is not None)


def _mlflow_client() -> MlflowClient | None:
    global _MLFLOW_CLIENT
    if not _mlflow_enabled():
        return None
    if _MLFLOW_CLIENT is None:
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        _MLFLOW_CLIENT = MlflowClient()
    return _MLFLOW_CLIENT


def _model_name_for_site(site_id: str) -> str:
    return f"{settings.mlflow_model_name_prefix}_{site_id}"


def _load_site_model(site_id: str) -> SiteModel | None:
    client = _mlflow_client()
    if client is None:
        return None

    model_name = _model_name_for_site(site_id)
    try:
        alias_info = client.get_model_version_by_alias(model_name, settings.mlflow_model_alias)
    except MlflowException:
        return None

    cached = _MODEL_CACHE.get(site_id)
    if cached is not None and cached.model_version == alias_info.version:
        return cached

    try:
        loaded_model = mlflow.pyfunc.load_model(
            f"models:/{model_name}@{settings.mlflow_model_alias}"
        )
    except MlflowException:
        return None

    site_model = SiteModel(
        model_name=model_name,
        model_version=str(alias_info.version),
        model=loaded_model,
    )
    _MODEL_CACHE[site_id] = site_model
    return site_model


def _build_latest_feature_row(db: Session, site: Site) -> tuple[pd.DataFrame, datetime] | None:
    recent_readings = list(
        db.scalars(
            select(Reading)
            .where(Reading.site_id == site.site_id, Reading.consumption_kwh.is_not(None))
            .order_by(Reading.measured_at.desc())
            .limit(MODEL_INPUT_WINDOW_MINUTES)
        )
    )
    if not recent_readings:
        return None

    recent_readings.reverse()
    frame = pd.DataFrame(
        {
            "site_id": [item.site_id for item in recent_readings],
            "measured_at": [item.measured_at for item in recent_readings],
            "consumption_kwh": [item.consumption_kwh for item in recent_readings],
            "temperature_celsius": [item.temperature_celsius for item in recent_readings],
            "humidity_percent": [item.humidity_percent for item in recent_readings],
            "site_type": [site.site_type for _ in recent_readings],
        }
    )
    features = build_feature_frame(frame)
    if features.empty:
        return None

    latest = recent_readings[-1]
    return features.tail(1), as_utc(latest.measured_at)


def model_metadata() -> dict[str, object]:
    """Describe prediction model routing used by backend."""
    if _mlflow_enabled():
        return {
            "model_name": f"{settings.mlflow_model_name_prefix}_<SITE_ID>",
            "model_version": settings.mlflow_model_alias,
            "trained_at": None,
            "horizon_minutes": PREDICTION_HORIZON_MINUTES,
            "test_metrics": {"mae": None, "rmse": None, "mape_percent": None},
            "availability": "mlflow",
            "mlflow_available": True,
        }
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


def _fallback_prediction_kwh(db: Session, site_id: str) -> float | None:
    recent = list(
        db.scalars(
            select(Reading.consumption_kwh)
            .where(Reading.site_id == site_id, Reading.consumption_kwh.is_not(None))
            .order_by(Reading.measured_at.desc())
            .limit(24)
        )
    )
    if not recent:
        return None
    return round(sum(recent) / len(recent), 3)


def refresh_stored_predictions(db: Session, now: datetime | None = None) -> int:
    """Persist one 120-minute forecast for the latest available reading of each site."""
    predicted_at = as_utc(now or datetime.now(UTC)).replace(second=0, microsecond=0)
    score_due_predictions(db, predicted_at)
    created = 0
    for site in db.scalars(select(Site).where(Site.status == "active")):
        feature_row = _build_latest_feature_row(db, site)
        if feature_row is None:
            continue
        features, measured_at = feature_row
        target_at = measured_at + timedelta(minutes=PREDICTION_HORIZON_MINUTES)

        model_name = settings.local_model_name
        model_version = settings.local_model_version
        predicted_kwh: float | None = None

        site_model = _load_site_model(site.site_id)
        if site_model is not None:
            prediction_values = site_model.model.predict(features)
            predicted_kwh = float(prediction_values[0])
            model_name = site_model.model_name
            model_version = site_model.model_version
        else:
            predicted_kwh = _fallback_prediction_kwh(db, site.site_id)

        if predicted_kwh is None:
            continue

        existing = db.scalar(
            select(Prediction.id).where(
                Prediction.site_id == site.site_id,
                Prediction.target_at == target_at,
                Prediction.model_version == model_version,
                Prediction.horizon_minutes == PREDICTION_HORIZON_MINUTES,
            )
        )
        if existing is not None:
            continue

        db.add(
            Prediction(
                site_id=site.site_id,
                predicted_at=predicted_at,
                target_at=target_at,
                horizon_minutes=PREDICTION_HORIZON_MINUTES,
                model_name=model_name,
                model_version=model_version,
                predicted_kwh=round(predicted_kwh, 3),
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
