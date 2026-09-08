"""Boucle de collecte : interroge la source et ecrit le brut, tel quel.

Rien n est interprete ici. Ce qui est jete a cet etage est perdu
definitivement, donc la reponse de la source part en base sans relecture.
"""

import json
import logging
import time

import httpx

LOGGER = logging.getLogger(__name__)

TIMEOUT_SECONDS = 10


class Collector:
    def __init__(self, interval: int, api_url: str, storage, client: httpx.Client | None = None):
        self.interval = interval
        self.api_url = api_url.rstrip("/")
        self.storage = storage
        self.client = client or httpx.Client(timeout=TIMEOUT_SECONDS)

    def run(self) -> None:
        """Boucle sans fin. Un passage rate n arrete pas le collecteur.

        La source peut tomber, le reseau de l ecole peut couper. Le collecteur
        journalise et retente au tour suivant, il ne meurt pas : un conteneur
        qui redemarre en boucle est plus difficile a diagnostiquer qu un
        journal qui repete la meme erreur.
        """
        LOGGER.info(
            "Collecteur demarre, un passage toutes les %d s, source %s",
            self.interval,
            self.api_url,
        )
        while True:
            try:
                self.run_once()
            except Exception:
                LOGGER.exception("Passage de collecte en echec, reprise au prochain tour")
            time.sleep(self.interval)

    def run_once(self) -> None:
        """Un passage : les deux referentiels, puis la mesure courante de chaque site."""
        sites = self._get("/api/v1/sites")
        self.storage.store_snapshot("api_sites", json.dumps(sites))
        self._store_sensor_snapshot()

        payloads = []
        for site in sites:
            site_id = site["site_id"]
            try:
                payloads.append(json.dumps(self._get(f"/api/v1/sites/{site_id}/current")))
            except Exception:
                # Un site injoignable ne doit pas priver les autres de leur mesure.
                LOGGER.exception("Site %s ignore pour ce passage", site_id)

        inserted = self.storage.store_raw_many("api_current", payloads)
        LOGGER.info(
            "Passage: %d/%d site(s) lus, %d mesure(s) inseree(s)",
            len(payloads),
            len(sites),
            inserted,
        )

    def _store_sensor_snapshot(self) -> None:
        """Enregistre l etat des capteurs.

        Un echec ici n empeche pas la collecte des mesures, qui est la raison
        d etre du passage. L etat des capteurs est un complement.
        """
        try:
            sensors = self._get("/api/v1/sensors/status")
        except Exception:
            LOGGER.exception("Etat des capteurs indisponible pour ce passage")
            return
        self.storage.store_snapshot("api_sensors", json.dumps(sensors))

    def _get(self, path: str):
        response = self.client.get(f"{self.api_url}{path}")
        response.raise_for_status()
        return response.json()
