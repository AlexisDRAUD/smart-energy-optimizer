"""Reprise unique de l'historique d'un site depuis la source, vers la zone brute.

Usage :
    python -m app.collector.backfill SITE001

Le pas de generation est fige a 1 mesure/minute : demander des fenetres
plus larges degrade les donnees generees par la source (constat du 03/09).
"""

import json
import sys
from datetime import datetime, timedelta

import httpx

from app.collector.config import database_url, source_api_url
from app.collector.storage import PostgresStorage

PROFONDEUR_JOURS = 730
FENETRE_MINUTES = 1000   # 1000 points sur 1000 minutes = 1 point/minute
LIMIT = 1000


class Backfill:
    def __init__(self, storage, client_api, site_id: str):
        self.storage = storage
        self.client_api = client_api
        self.site_id = site_id

    def run(self) -> None:
        fin = datetime.now().replace(second=0, microsecond=0)
        debut = fin - timedelta(days=PROFONDEUR_JOURS)

        curseur = debut
        while curseur < fin:
            fin_fenetre = min(curseur + timedelta(minutes=FENETRE_MINUTES), fin)
            limit = int((fin_fenetre - curseur).total_seconds() / 60)
            mesures = self.client_api(self.site_id, curseur, fin_fenetre, limit)
            for mesure in mesures:
                self.storage.store_raw(source="api_backfill", payload=json.dumps(mesure))
            curseur = fin_fenetre


def client_api_reel(site_id, start_time, end_time, limit):
    reponse = httpx.get(
        f"{source_api_url()}/api/v1/readings",
        params={
            "site_id": site_id,
            "start_time": start_time.isoformat(timespec="seconds"),
            "end_time": end_time.isoformat(timespec="seconds"),
            "limit": limit,
        },
        timeout=60,
    )
    reponse.raise_for_status()
    return reponse.json()


if __name__ == "__main__":
    site_id = sys.argv[1]
    storage = PostgresStorage(database_url())
    Backfill(storage, client_api_reel, site_id).run()
    storage.close()
