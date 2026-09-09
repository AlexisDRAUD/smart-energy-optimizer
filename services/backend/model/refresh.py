"""Boucle d'ecriture des previsions du worker.

Pour chaque site actif, une prevision a l'horizon configure est ecrite dans
``predictions`` a partir du modele versionne du site dans le registre MLflow
(``model.forecast``). Un site sans modele publie, ou un registre injoignable,
est simplement ignore : ce worker ne sert que des modeles MLflow.

Il rapproche aussi les previsions arrivees a echeance de la mesure reelle
(``_score_due``) : c'est un rapprochement en base, pas un calcul de modele.

L'idempotence tient a la contrainte d'unicite
``site_id, target_at, model_version, horizon_minutes`` : rejouer un passage sans
nouveau releve n'ecrit rien.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.config import settings
from app.core.contract import as_utc
from app.db.models.prediction import Prediction
from app.db.models.reading import Reading
from app.db.models.site import Site
from sqlalchemy import select
from sqlalchemy.orm import Session

from model.forecast import SiteForecaster


def _score_due(db: Session, scored_at: datetime) -> int:
    """Attacher la mesure reelle aux previsions dont l'echeance est passee."""
    scored = 0
    due = db.scalars(
        select(Prediction).where(
            Prediction.actual_kwh.is_(None),
            Prediction.target_at <= scored_at,
        )
    )
    for prediction in due:
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


def refresh_predictions(
    db: Session,
    forecaster: SiteForecaster | None = None,
    now: datetime | None = None,
) -> int:
    """Ecrire une prevision par site actif disposant d'un modele. Renvoie le nombre cree."""
    predicted_at = as_utc(now or datetime.now(UTC)).replace(second=0, microsecond=0)
    _score_due(db, predicted_at)
    horizon = settings.prediction_horizon_minutes
    created = 0

    if forecaster is None:
        db.commit()
        return 0

    for site in db.scalars(select(Site).where(Site.status == "active")):
        # Dernier releve REEL du site : le forecaster ancre ses variables sur ce
        # meme releve (``forecast._recent_source`` filtre ``consumption_kwh``
        # non nul). Prendre ici la derniere ligne sans egard a la valeur
        # decalerait ``target_at`` de plusieurs minutes quand les derniers
        # releves sont nuls, alors que la prevision partirait d'un instant
        # anterieur.
        latest = db.scalar(
            select(Reading)
            .where(
                Reading.site_id == site.site_id,
                Reading.consumption_kwh.is_not(None),
            )
            .order_by(Reading.measured_at.desc())
            .limit(1)
        )
        if latest is None:
            continue

        forecast = forecaster.forecast(db, site, latest)
        if forecast is None:
            continue
        predicted_kwh, model_name, model_version = forecast

        target_at = as_utc(latest.measured_at) + timedelta(minutes=horizon)
        existing = db.scalar(
            select(Prediction.id).where(
                Prediction.site_id == site.site_id,
                Prediction.target_at == target_at,
                Prediction.model_version == model_version,
                Prediction.horizon_minutes == horizon,
            )
        )
        if existing is not None:
            continue

        db.add(
            Prediction(
                site_id=site.site_id,
                predicted_at=predicted_at,
                target_at=target_at,
                horizon_minutes=horizon,
                model_name=model_name,
                model_version=model_version,
                predicted_kwh=predicted_kwh,
                actual_kwh=None,
                scored_at=None,
            )
        )
        created += 1
    db.commit()
    return created
