"""Boucle de prevision : rejoue les modeles MLflow a intervalle regulier (60 s).

A chaque passage (cf. ``model/refresh.py``), pour chaque site actif :

1. lecture du dernier releve du site dans ``readings`` ;
2. prevision a l'horizon configure par le modele versionne du site dans le
   registre MLflow (``EnerVision_RF_Predictor_<site_id>`` alias ``production``,
   cf. ``model/forecast.py``). Un site sans modele publie est ignore ;
3. ecriture d'une ligne dans ``predictions`` (ignoree si identique) ;
4. rapprochement des previsions arrivees a echeance avec la mesure reelle.

Ce worker ne sert que des modeles MLflow : aucun repli local. La cadence vient de
cette boucle, pas d'un ordonnanceur externe ; le conteneur tourne en continu
avec ``restart: unless-stopped`` (cf. docker-compose.yml).
"""

from __future__ import annotations

import argparse
import logging
import signal
import threading
from types import FrameType

from app.config import settings
from app.db.models.prediction import Prediction
from app.db.session import SessionLocal, verify_database_connection
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from model.forecast import SiteForecaster, build_forecaster
from model.refresh import refresh_predictions

LOGGER = logging.getLogger(__name__)

_stop = threading.Event()

# Construit au premier passage puis reutilise : le forecaster garde en cache le
# modele deja telecharge de chaque site. ``_forecaster_ready`` distingue "pas
# encore tente" de "tente, aucun modele" (``None``).
_forecaster: SiteForecaster | None = None
_forecaster_ready = False


def _get_forecaster() -> SiteForecaster | None:
    global _forecaster, _forecaster_ready
    if not _forecaster_ready:
        _forecaster = build_forecaster()
        _forecaster_ready = True
        if _forecaster is None:
            LOGGER.warning(
                "MLFLOW_TRACKING_URI absent : aucun modele a servir, aucune prevision ecrite"
            )
        else:
            LOGGER.info(
                "Previsions par modele MLflow %s@%s",
                settings.mlflow_model_name_prefix,
                settings.mlflow_model_alias,
            )
    return _forecaster


def _request_stop(signum: int, _frame: FrameType | None) -> None:
    LOGGER.info("Signal %s recu, arret apres le passage en cours", signal.Signals(signum).name)
    _stop.set()


def run_once() -> int:
    """Un passage complet. Renvoie le nombre de previsions creees."""
    forecaster = _get_forecaster()
    with SessionLocal() as db:
        created = refresh_predictions(db, forecaster)
        total = db.scalar(select(func.count()).select_from(Prediction)) or 0
    LOGGER.info(
        "Passage termine: previsions_creees=%d horizon_minutes=%d total_en_base=%d",
        created,
        settings.prediction_horizon_minutes,
        total,
    )
    return created


def loop(interval_seconds: int) -> int:
    """Boucle jusqu a reception d un signal d arret."""
    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)

    verify_database_connection()
    LOGGER.info("Worker de prevision demarre, cadence=%ds", interval_seconds)

    while not _stop.is_set():
        try:
            run_once()
        except SQLAlchemyError:
            LOGGER.exception("Passage de prevision en echec, nouvelle tentative au prochain cycle")
        _stop.wait(timeout=interval_seconds)

    LOGGER.info("Worker de prevision arrete")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Worker de prevision EnerVision")
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=settings.prediction_worker_interval_seconds,
        help="intervalle entre deux passages (defaut: %(default)s)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="faire un seul passage puis quitter (utile pour un cron ou un test)",
    )
    return parser


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args()
    if args.once:
        run_once()
        return 0
    return loop(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
