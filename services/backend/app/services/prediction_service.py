from __future__ import annotations

from datetime import UTC, datetime, timedelta
from math import sqrt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.contract import as_utc, utc_iso
from app.db.models.prediction import Prediction
from app.db.models.reading import Reading
from app.db.models.site import Site
from app.services.prediction_alerts import evaluate_prediction_rise


def model_metadata(db: Session, site_id: str | None = None) -> dict[str, object]:
    """Decrire le modele en service a partir des previsions reellement ecrites.

    Rien n est declare ici : le nom, la version et l horizon sont ceux de la
    derniere ligne de la table predictions. Tant qu aucune prevision n existe,
    les champs sont nuls plutot que remplis avec des valeurs de facade.

    Avec ``site_id``, tout est restreint aux previsions de ce site : le modele
    decrit est alors celui qui sert reellement ce site (un modele MLflow par
    site), et les compteurs ne portent que sur lui.
    """
    latest_stmt = select(Prediction).order_by(Prediction.predicted_at.desc(), Prediction.id.desc())
    total_stmt = select(func.count()).select_from(Prediction)
    scored_stmt = (
        select(func.count()).select_from(Prediction).where(Prediction.actual_kwh.is_not(None))
    )
    if site_id is not None:
        latest_stmt = latest_stmt.where(Prediction.site_id == site_id)
        total_stmt = total_stmt.where(Prediction.site_id == site_id)
        scored_stmt = scored_stmt.where(Prediction.site_id == site_id)

    latest = db.scalar(latest_stmt.limit(1))
    total = db.scalar(total_stmt) or 0
    scored = db.scalar(scored_stmt) or 0
    return {
        "model_name": latest.model_name if latest else None,
        "model_version": latest.model_version if latest else None,
        "horizon_minutes": latest.horizon_minutes if latest else None,
        "last_prediction_at": utc_iso(latest.predicted_at) if latest else None,
        "predictions_total": total,
        "predictions_scored": scored,
    }


def active_model(db: Session, site_id: str) -> tuple[str, str] | None:
    """Nom et version du modele qui sert le site : ceux de sa derniere prevision.

    Un site est servi par un seul modele a la fois (un modele MLflow par site).
    Renvoie ``None`` quand le site n a encore aucune prevision.
    """
    row = db.execute(
        select(Prediction.model_name, Prediction.model_version)
        .where(Prediction.site_id == site_id)
        .order_by(Prediction.predicted_at.desc(), Prediction.id.desc())
        .limit(1)
    ).first()
    return None if row is None else (row.model_name, row.model_version)


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
    """Ecrire une prevision par site a l horizon configure, pour son dernier releve."""
    predicted_at = as_utc(now or datetime.now(UTC)).replace(second=0, microsecond=0)
    score_due_predictions(db, predicted_at)
    horizon = settings.prediction_horizon_minutes
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

        target_at = as_utc(latest.measured_at) + timedelta(minutes=horizon)
        existing = db.scalar(
            select(Prediction.id).where(
                Prediction.site_id == site.site_id,
                Prediction.target_at == target_at,
                Prediction.model_version == settings.local_model_version,
                Prediction.horizon_minutes == horizon,
            )
        )
        if existing is not None:
            continue

        predicted_kwh = _fallback_prediction_kwh(db, site.site_id)
        if predicted_kwh is None:
            continue

        db.add(
            Prediction(
                site_id=site.site_id,
                predicted_at=predicted_at,
                target_at=target_at,
                horizon_minutes=horizon,
                model_name=settings.local_model_name,
                model_version=settings.local_model_version,
                predicted_kwh=predicted_kwh,
                actual_kwh=None,
                scored_at=None,
            )
        )
        created += 1

        # La prevision qui vient d etre ecrite est comparee au dernier releve
        # reel du site : une montee trop rapide devient une alerte ouverte.
        if latest.consumption_kwh is not None:
            evaluate_prediction_rise(
                db,
                site_id=site.site_id,
                baseline_kwh=latest.consumption_kwh,
                predicted_kwh=predicted_kwh,
                horizon_minutes=horizon,
                detected_at=predicted_at,
            )
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
