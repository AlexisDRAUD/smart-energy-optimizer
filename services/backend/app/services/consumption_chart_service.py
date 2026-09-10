"""Bounded display series. Business results use full data; only payloads use LTTB."""

from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, load_only

from app.api.v1.serializers import prediction_response
from app.config import settings
from app.core.contract import as_utc, utc_iso
from app.db.models.prediction import Prediction
from app.db.models.reading import Reading
from app.services.lttb import downsample_with_gaps

MAX_DAYS = 30
HORIZON_MINUTES = 120
CADENCE_SECONDS = 60
# Arbitrary second boundaries can touch one extra UTC minute.
MAX_READINGS = MAX_DAYS * 1440 + 1
MAX_PREDICTIONS = MAX_READINGS + HORIZON_MINUTES
DISPLAY_POINTS_PER_SERIES = 600


def active_model(db: Session, site_id: str) -> tuple[str, str]:
    """Modele (nom, version) de la derniere prevision du site.

    Le graphique suit ce modele : les series historiques et futures sont filtrees
    sur ce couple exact, et l'identite renvoyee est celle des lignes reellement
    ecrites (moyenne mobile locale ou modele MLflow par site, selon ce que le
    worker sert). Sans aucune prevision pour le site, on retombe sur le modele
    local par defaut pour garder une reponse de forme constante.
    """
    row = db.execute(
        select(Prediction.model_name, Prediction.model_version)
        .where(
            Prediction.site_id == site_id,
            Prediction.horizon_minutes == HORIZON_MINUTES,
        )
        .order_by(Prediction.predicted_at.desc(), Prediction.id.desc())
        .limit(1)
    ).first()
    if row is None:
        return settings.local_model_name, settings.local_model_version
    return row.model_name, row.model_version


def sampling_stats(source: list[dict], displayed: list[dict]) -> dict[str, int | bool]:
    return {
        "input_points": len(source),
        "output_points": len(displayed),
        "applied": len(displayed) < len(source),
    }


def coverage(
    points: list[dict], time_key: str, value_key: str, start: datetime, end: datetime
) -> dict:
    first = start.replace(second=0, microsecond=0)
    last = (end - timedelta(microseconds=1)).replace(second=0, microsecond=0)
    expected = int((last - first).total_seconds() / CADENCE_SECONDS) + 1
    received = {
        as_utc(datetime.fromisoformat(p[time_key])).replace(second=0, microsecond=0) for p in points
    }
    valid = {
        as_utc(datetime.fromisoformat(p[time_key])).replace(second=0, microsecond=0)
        for p in points
        if p[value_key] is not None
    }
    return {
        "expected_minutes": expected,
        "received_minutes": len(received),
        "missing_minutes": expected - len(received),
        "null_minutes": len(received - valid),
        "valid_minutes": len(valid),
        "percent": round(len(valid) / expected * 100, 2),
        "first_at": points[0][time_key] if points else None,
        "last_at": points[-1][time_key] if points else None,
    }


def consumption_chart(db: Session, site_id: str, start: datetime, end: datetime) -> dict:
    future_end = end + timedelta(minutes=HORIZON_MINUTES)
    model_name, model_version = active_model(db, site_id)
    # Existing indexes start with (site_id, measured_at) / (site_id, target_at).
    # LIMIT + 1 detects overflow, never returns a partial series as a success.
    readings = list(
        db.scalars(
            select(Reading)
            .options(
                load_only(
                    Reading.site_id,
                    Reading.measured_at,
                    Reading.consumption_kwh,
                    Reading.is_imputed,
                    Reading.data_quality,
                )
            )
            .where(
                Reading.site_id == site_id,
                Reading.measured_at >= start,
                Reading.measured_at < end,
            )
            .order_by(Reading.measured_at)
            .limit(MAX_READINGS + 1)
        )
    )
    predictions = list(
        db.scalars(
            select(Prediction)
            .where(
                Prediction.site_id == site_id,
                Prediction.target_at >= start,
                Prediction.target_at < future_end,
                Prediction.horizon_minutes == HORIZON_MINUTES,
                Prediction.model_name == model_name,
                Prediction.model_version == model_version,
            )
            .order_by(Prediction.target_at, Prediction.id)
            .limit(MAX_PREDICTIONS + 1)
        )
    )
    if len(readings) > MAX_READINGS or len(predictions) > MAX_PREDICTIONS:
        raise HTTPException(422, "Chart volume exceeds the supported limit; shorten the window")

    points = [
        {
            "measured_at": utc_iso(r.measured_at),
            "consumption_kwh": r.consumption_kwh,
            "is_imputed": r.is_imputed,
            "data_quality": r.data_quality,
        }
        for r in readings
    ]
    historical = [prediction_response(p) for p in predictions if as_utc(p.target_at) < end]
    future = [prediction_response(p) for p in predictions if as_utc(p.target_at) >= end]

    # Same exact timestamp and site, using current native readings, without writing a score.
    actuals = {p["measured_at"]: p["consumption_kwh"] for p in points}
    last_evaluated = None
    for prediction in reversed(historical):
        actual = actuals.get(prediction["target_at"])
        if actual is not None:
            predicted = prediction["predicted_kwh"]
            last_evaluated = {
                "target_at": prediction["target_at"],
                "actual_kwh": actual,
                "predicted_kwh": predicted,
                "deviation_percent": (actual - predicted) / predicted * 100 if predicted else None,
                "horizon_minutes": HORIZON_MINUTES,
                "model_version": prediction["model_version"],
            }
            break

    # Coverage and comparison use the complete native series. LTTB only shapes the payload.
    reading_coverage = coverage(points, "measured_at", "consumption_kwh", start, end)
    prediction_coverage = coverage(historical, "target_at", "predicted_kwh", start, end)
    future_coverage = coverage(future, "target_at", "predicted_kwh", end, future_end)
    displayed_points = downsample_with_gaps(
        points,
        time_key="measured_at",
        value_key="consumption_kwh",
        threshold=DISPLAY_POINTS_PER_SERIES,
        cadence_seconds=CADENCE_SECONDS,
    )
    displayed_historical = downsample_with_gaps(
        historical,
        time_key="target_at",
        value_key="predicted_kwh",
        threshold=DISPLAY_POINTS_PER_SERIES,
        cadence_seconds=CADENCE_SECONDS,
    )
    displayed_future = downsample_with_gaps(
        future,
        time_key="target_at",
        value_key="predicted_kwh",
        threshold=DISPLAY_POINTS_PER_SERIES,
        cadence_seconds=CADENCE_SECONDS,
    )

    return {
        "site_id": site_id,
        "start": utc_iso(start),
        "end": utc_iso(end),
        "future_end": utc_iso(future_end),
        "unit": "kWh",
        "unit_basis": "source_declared",
        "measurement_interval_seconds": None,
        "cadence_seconds": CADENCE_SECONDS,
        "horizon_minutes": HORIZON_MINUTES,
        "model_name": model_name,
        "model_version": model_version,
        "max_readings": MAX_READINGS,
        "max_predictions": MAX_PREDICTIONS,
        "readings": displayed_points,
        "historical_predictions": displayed_historical,
        "future_predictions": displayed_future,
        "reading_coverage": reading_coverage,
        "prediction_coverage": prediction_coverage,
        "future_coverage": future_coverage,
        "downsampling": {
            "algorithm": "lttb",
            "target_points_per_series": DISPLAY_POINTS_PER_SERIES,
            "readings": sampling_stats(points, displayed_points),
            "historical_predictions": sampling_stats(historical, displayed_historical),
            "future_predictions": sampling_stats(future, displayed_future),
        },
        "last_evaluated": last_evaluated,
    }
