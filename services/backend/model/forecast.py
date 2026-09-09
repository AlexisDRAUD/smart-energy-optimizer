"""Prevision par modele MLflow, un modele par site.

Le registre MLflow versionne un modele ``EnerVision_RF_Predictor_<site_id>`` par
site, avec l'alias ``production`` sur la version a servir. Ce module resout cet
alias, telecharge le modele (mis en cache par version) et l'applique aux
variables du dernier releve du site. Il ne connait du modele que ce que le
registre expose : ni son entrainement, ni son code source.

Les variables d'entree sont calculees par ``seo_features.build_feature_frame``
(paquet ``packages/features``), la formule partagee avec l'entrainement : la
reecrire ici ferait diverger le service du modele sans qu'aucun test n'echoue.

Quand le registre est injoignable, qu'aucun modele n'existe encore pour le site
ou que la prevision echoue, ``SiteForecaster.forecast`` renvoie ``None`` et
``model.refresh.refresh_predictions`` n'ecrit rien pour ce site. Le worker ne
doit jamais s'arreter parce que MLflow a hoquete.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import NamedTuple

import mlflow
import numpy as np
import pandas as pd
from app.config import settings
from app.db.models.reading import Reading
from app.db.models.site import Site
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient
from seo_features import build_feature_frame
from sqlalchemy import select
from sqlalchemy.orm import Session

LOGGER = logging.getLogger(__name__)

# Fenetre de releves passee au calcul des variables. Les retards du package vont
# jusqu'a 120 observations (``lag_120``, ``rolling_mean_120``) ; 240 lignes
# laissent ces variables pleinement renseignees pour le dernier releve.
_HISTORY_ROWS = 240


class SiteForecast(NamedTuple):
    """Resultat d'une prevision : valeur et identite du modele qui l'a produite."""

    predicted_kwh: float
    model_name: str
    model_version: str


class _LoadedModel(NamedTuple):
    version: str
    model: object


class SiteForecaster:
    """Charge et applique le modele MLflow ``production`` de chaque site.

    Un seul objet vit pour toute la duree du worker : il garde en cache le
    modele deja telecharge de chaque site et ne le recharge que lorsque l'alias
    ``production`` pointe vers une nouvelle version.
    """

    def __init__(
        self,
        tracking_uri: str,
        *,
        model_prefix: str = settings.mlflow_model_name_prefix,
        alias: str = settings.mlflow_model_alias,
    ) -> None:
        mlflow.set_tracking_uri(tracking_uri)
        self._client = MlflowClient(tracking_uri=tracking_uri)
        self._model_prefix = model_prefix
        self._alias = alias
        self._models: dict[str, _LoadedModel] = {}
        # Sites deja signales comme sans modele : on ne le journalise qu'une fois.
        self._unavailable: set[str] = set()

    def _registered_name(self, site_id: str) -> str:
        return f"{self._model_prefix}_{site_id}"

    def _load(self, site_id: str) -> _LoadedModel | None:
        """Modele ``production`` du site, mis en cache par version. None si aucun.

        Toute erreur (alias absent, registre injoignable, artefact illisible) est
        traitee comme "pas de modele pour l'instant" : journalisee une fois par
        site, puis aucune prevision n'est ecrite pour ce site.
        """
        name = self._registered_name(site_id)
        try:
            version = self._client.get_model_version_by_alias(name, self._alias)
            cached = self._models.get(site_id)
            if cached is not None and cached.version == str(version.version):
                return cached
            model = mlflow.pyfunc.load_model(f"models:/{name}/{version.version}")
        except (MlflowException, OSError) as exc:
            if site_id not in self._unavailable:
                LOGGER.info(
                    "Modele %s@%s indisponible (%s), site %s sans prevision",
                    name,
                    self._alias,
                    type(exc).__name__,
                    site_id,
                )
                self._unavailable.add(site_id)
            return None

        loaded = _LoadedModel(version=str(version.version), model=model)
        self._models[site_id] = loaded
        self._unavailable.discard(site_id)
        LOGGER.info("Modele %s version %s charge pour %s", name, version.version, site_id)
        return loaded

    def _recent_source(self, db: Session, site: Site, until: datetime) -> pd.DataFrame:
        rows = db.execute(
            select(
                Reading.measured_at,
                Reading.consumption_kwh,
                Reading.temperature_celsius,
                Reading.humidity_percent,
            )
            .where(
                Reading.site_id == site.site_id,
                Reading.consumption_kwh.is_not(None),
                Reading.measured_at <= until,
            )
            .order_by(Reading.measured_at.desc())
            .limit(_HISTORY_ROWS)
        ).all()
        if not rows:
            return pd.DataFrame()
        frame = pd.DataFrame(
            rows,
            columns=[
                "measured_at",
                "consumption_kwh",
                "temperature_celsius",
                "humidity_percent",
            ],
        )
        frame["site_id"] = site.site_id
        frame["site_type"] = site.site_type or "unknown"
        return frame

    def forecast(self, db: Session, site: Site, latest: Reading) -> SiteForecast | None:
        """Prevision a l'horizon pour ``site``, ancree sur ``latest``.

        ``latest`` est le dernier releve du site : le modele voit les variables
        calculees a cet instant et predit la consommation ``horizon`` minutes
        plus tard, exactement comme a l'entrainement.
        """
        try:
            loaded = self._load(site.site_id)
            if loaded is None:
                return None
            source = self._recent_source(db, site, latest.measured_at)
            if source.empty:
                return None
            features = build_feature_frame(source).tail(1)
            raw = loaded.model.predict(features)
            predicted = float(np.asarray(raw).reshape(-1)[0])
        except (MlflowException, ValueError, KeyError, OSError, IndexError):
            LOGGER.warning(
                "Prevision MLflow en echec pour %s, site sans prevision ce passage",
                site.site_id,
                exc_info=True,
            )
            return None

        if not math.isfinite(predicted):
            return None
        return SiteForecast(
            predicted_kwh=round(predicted, 3),
            model_name=self._registered_name(site.site_id),
            model_version=loaded.version,
        )


def build_forecaster() -> SiteForecaster | None:
    """Construit le forecaster si ``MLFLOW_TRACKING_URI`` est configure, sinon None.

    Sans adresse de suivi (tests, deploiement sans MLflow), le worker n'ecrit
    aucune prevision : il ne sert que des modeles du registre.
    """
    if not settings.mlflow_tracking_uri:
        return None
    return SiteForecaster(settings.mlflow_tracking_uri)
