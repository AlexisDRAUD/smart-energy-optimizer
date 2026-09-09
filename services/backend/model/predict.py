"""Boucle de prevision : rejoue le modele a intervalle regulier (60 s par defaut).

A chaque passage, pour chaque site actif, ``refresh_stored_predictions`` :

1. lit le dernier releve du site dans ``readings`` ;
2. calcule une prevision a l'horizon configure (moyenne des 24 derniers releves,
   modele ``local-moving-average`` ; cette branche n'a pas d'integration MLflow) ;
3. ecrit une ligne dans ``predictions`` (ignoree si une prevision identique
   existe deja) ;
4. rapproche les previsions arrivees a echeance avec la mesure reelle.

Le calcul est celui de ``app.services.prediction_service``, partage avec l'API.
La cadence vient de cette boucle, pas d'un ordonnanceur externe : le conteneur
tourne en continu avec ``restart: unless-stopped`` (cf. docker-compose.yml).
"""

from __future__ import annotations

import argparse
import logging
import signal
import threading
from types import FrameType

from app.config import settings
from app.db.session import SessionLocal, verify_database_connection
from app.services.prediction_service import model_metadata, refresh_stored_predictions
from sqlalchemy.exc import SQLAlchemyError

LOGGER = logging.getLogger(__name__)

_stop = threading.Event()


def _request_stop(signum: int, _frame: FrameType | None) -> None:
    LOGGER.info("Signal %s recu, arret apres le passage en cours", signal.Signals(signum).name)
    _stop.set()


def run_once() -> int:
    """Un passage complet. Renvoie le nombre de previsions creees."""
    with SessionLocal() as db:
        created = refresh_stored_predictions(db)
        meta = model_metadata(db)
    LOGGER.info(
        "Passage termine: previsions_creees=%d horizon_minutes=%d modele=%s total_en_base=%s",
        created,
        settings.prediction_horizon_minutes,
        meta["model_name"],
        meta["predictions_total"],
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
