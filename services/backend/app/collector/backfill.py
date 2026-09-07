"""Reprise de l historique depuis la source, vers la zone brute.

Usage :
    python -m app.collector.backfill              # tous les sites, BACKFILL_DAYS
    python -m app.collector.backfill --site SITE001 --days 2
    python -m app.collector.backfill --force      # meme si la base est remplie

Le pas de generation est fige a 1 mesure/minute : demander des fenetres plus
larges degrade les donnees generees par la source (constat du 03/09).
"""

import argparse
import json
import logging
from collections.abc import Sequence
from datetime import datetime, timedelta

import httpx
from sqlalchemy import text

from app.collector.storage import PostgresStorage
from app.config import settings

LOGGER = logging.getLogger(__name__)

FENETRE_MINUTES = 1000  # 1000 points sur 1000 minutes = 1 point/minute
TIMEOUT_SECONDS = 60


class Backfill:
    """Reprise de l historique d un seul site."""

    def __init__(self, storage, client_api, site_id: str, days: int | None = None):
        self.storage = storage
        self.client_api = client_api
        self.site_id = site_id
        self.days = settings.backfill_days if days is None else days

    def run(self) -> int:
        """Rend le nombre de mesures reellement inserees."""
        fin = datetime.now().replace(second=0, microsecond=0)
        debut = fin - timedelta(days=self.days)

        inserees = 0
        curseur = debut
        while curseur < fin:
            fin_fenetre = min(curseur + timedelta(minutes=FENETRE_MINUTES), fin)
            limit = int((fin_fenetre - curseur).total_seconds() / 60)
            mesures = self.client_api(self.site_id, curseur, fin_fenetre, limit)
            # Une insertion par lot et non une par mesure : la reprise ecrit des
            # dizaines de milliers de lignes.
            inserees += self.storage.store_raw_many(
                "api_backfill", [json.dumps(mesure) for mesure in mesures]
            )
            curseur = fin_fenetre

        LOGGER.info(
            "Site %s: %d mesure(s) reprises sur %d jour(s)", self.site_id, inserees, self.days
        )
        return inserees


def already_populated(storage) -> bool:
    """Vrai des qu une mesure brute existe deja.

    L endpoint historique regenere les donnees a chaque appel : une seconde
    reprise ecrirait des valeurs differentes de celles deja en base. La garde
    protege de cela, pas des doublons, dont la cle unique se charge deja.
    """
    with storage.engine.connect() as conn:
        return conn.execute(text("SELECT EXISTS (SELECT 1 FROM raw_readings)")).scalar()


def run_backfill(storage, client_api, site_ids: Sequence[str], days: int | None = None) -> int:
    """Reprend l historique de chaque site.

    Un site en erreur n arrete pas les autres : la source peut refuser un site
    et repondre pour les suivants, autant garder ce qu on peut.
    """
    total = 0
    for site_id in site_ids:
        try:
            total += Backfill(storage, client_api, site_id, days).run()
        except Exception:
            LOGGER.exception("Reprise du site %s abandonnee", site_id)
    return total


def _client() -> httpx.Client:
    return httpx.Client(base_url=settings.source_api_base_url, timeout=TIMEOUT_SECONDS)


def lire_les_sites(client: httpx.Client) -> list[dict]:
    reponse = client.get("/api/v1/sites")
    reponse.raise_for_status()
    return reponse.json()


def client_api_reel(client: httpx.Client):
    """Fabrique la fonction d appel attendue par Backfill."""

    def appeler(site_id, start_time, end_time, limit):
        reponse = client.get(
            "/api/v1/readings",
            params={
                "site_id": site_id,
                "start_time": start_time.isoformat(timespec="seconds"),
                "end_time": end_time.isoformat(timespec="seconds"),
                "limit": limit,
            },
        )
        reponse.raise_for_status()
        return reponse.json()

    return appeler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reprise de l historique EnerVision")
    parser.add_argument(
        "--site",
        action="append",
        dest="sites",
        metavar="SITE_ID",
        help="limite la reprise a ce site, repetable. Par defaut, tous les sites.",
    )
    parser.add_argument(
        "--days",
        type=int,
        help=f"profondeur en jours (defaut: BACKFILL_DAYS, soit {settings.backfill_days})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="reprend meme si des mesures brutes existent deja",
    )
    return parser


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    arguments = build_parser().parse_args()

    storage = PostgresStorage(settings.database_url)
    try:
        if already_populated(storage) and not arguments.force:
            LOGGER.info(
                "Des mesures brutes existent deja, reprise ignoree. --force pour passer outre."
            )
            return 0

        with _client() as client:
            sites = lire_les_sites(client)
            # Le referentiel part en base des maintenant : sans lui l API repond
            # 404 sur tout jusqu au premier passage du collecteur.
            storage.store_snapshot("api_sites", json.dumps(sites))

            site_ids = arguments.sites or [site["site_id"] for site in sites]
            total = run_backfill(storage, client_api_reel(client), site_ids, arguments.days)

        LOGGER.info("Reprise terminee: %d mesure(s) sur %d site(s)", total, len(site_ids))
    finally:
        storage.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
