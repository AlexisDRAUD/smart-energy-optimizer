"""Reprise de l historique depuis la source, vers la zone brute.

Usage :
    python -m app.collector.backfill              # tous les sites, BACKFILL_DAYS
    python -m app.collector.backfill --site SITE001 --days 2
    python -m app.collector.backfill --force      # meme les sites deja repris

Le pas de generation est fige a 1 mesure/minute : demander des fenetres plus
larges degrade les donnees generees par la source (constat du 03/09).

Relancer est sans effet sur un site qui a deja son historique : il est saute.
Un site en echec, lui, ne laisse aucune ligne, le demarrage suivant le reprend
donc de lui-meme.
"""

import argparse
import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
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
        """Rend le nombre de mesures reellement inserees.

        Tout ou rien pour ce site : les fenetres sont d abord toutes lues, puis
        ecrites en un seul appel, donc dans une seule transaction. Un site dont
        la source coupe a mi-parcours ne laisse aucune ligne, il se distingue
        donc d un site repris. C est cette propriete qui permet a la garde de
        raisonner par site, et au demarrage suivant de reprendre celui qui a
        echoue au lieu de le laisser a moitie repris pour toujours.

        Les appels restent hors de la transaction : la tenir ouverte le temps
        d une dizaine d allers-retours reseau bloquerait le nettoyage de la
        table pour rien.
        """
        fin = datetime.now().replace(second=0, microsecond=0)
        debut = fin - timedelta(days=self.days)

        mesures = []
        curseur = debut
        while curseur < fin:
            fin_fenetre = min(curseur + timedelta(minutes=FENETRE_MINUTES), fin)
            limit = int((fin_fenetre - curseur).total_seconds() / 60)
            mesures.extend(self.client_api(self.site_id, curseur, fin_fenetre, limit))
            curseur = fin_fenetre

        # Une insertion par lot et non une par mesure : la reprise ecrit des
        # dizaines de milliers de lignes.
        inserees = self.storage.store_raw_many(
            "api_backfill", [json.dumps(mesure) for mesure in mesures]
        )

        LOGGER.info(
            "Site %s: %d mesure(s) reprises sur %d jour(s)", self.site_id, inserees, self.days
        )
        return inserees


def sites_deja_repris(storage) -> set[str]:
    """Les sites qui ont deja leur historique en base.

    L endpoint historique regenere les donnees a chaque appel : reprendre un
    site deja repris melangerait deux generations dans la meme serie. La garde
    protege de cela, pas des doublons, dont la cle unique se charge deja.

    Elle est par site, et non globale. Globale, un seul site repris suffisait a
    declarer toute la reprise faite : un site en echec n etait alors jamais
    repris, meme au demarrage suivant, et son historique manquait pour de bon.

    Seules les lignes de source api_backfill comptent. Le collecteur ecrit lui
    aussi dans raw_readings, et compter ses lignes ferait passer pour repris un
    site dont on n a que les dernieres minutes.
    """
    with storage.engine.connect() as conn:
        return set(
            conn.execute(
                text("SELECT DISTINCT site_id FROM raw_readings WHERE source = 'api_backfill'")
            ).scalars()
        )


@dataclass(frozen=True)
class BackfillCounts:
    """Ce qu une reprise a ecrit, saute et rate."""

    inserted: int = 0
    backfilled: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    failed: tuple[str, ...] = ()


def run_backfill(
    storage,
    client_api,
    site_ids: Sequence[str],
    days: int | None = None,
    force: bool = False,
) -> BackfillCounts:
    """Reprend l historique des sites qui n ont pas encore le leur.

    Un site en erreur n arrete pas les autres : la source peut refuser un site
    et repondre pour les suivants, autant garder ce qu on peut. Il est nomme
    dans le compte rendu, et comme un site en echec ne laisse aucune ligne, le
    demarrage suivant le reprend de lui-meme.
    """
    deja_repris = set() if force else sites_deja_repris(storage)

    inserted = 0
    backfilled: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []
    for site_id in site_ids:
        if site_id in deja_repris:
            skipped.append(site_id)
            continue
        try:
            inserted += Backfill(storage, client_api, site_id, days).run()
            backfilled.append(site_id)
        except Exception:
            LOGGER.exception("Reprise du site %s abandonnee", site_id)
            failed.append(site_id)

    return BackfillCounts(
        inserted=inserted,
        backfilled=tuple(backfilled),
        skipped=tuple(skipped),
        failed=tuple(failed),
    )


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
        help="reprend meme les sites dont l historique est deja en base",
    )
    return parser


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    arguments = build_parser().parse_args()

    storage = PostgresStorage(settings.database_url)
    try:
        with _client() as client:
            sites = lire_les_sites(client)
            # Le referentiel part en base des maintenant : sans lui l API repond
            # 404 sur tout jusqu au premier passage du collecteur.
            storage.store_snapshot("api_sites", json.dumps(sites))

            site_ids = arguments.sites or [site["site_id"] for site in sites]
            counts = run_backfill(
                storage, client_api_reel(client), site_ids, arguments.days, arguments.force
            )
    # Large volontairement : une source injoignable est une reprise en echec,
    # pas une trace d exception a dechiffrer dans le journal de demarrage.
    except Exception:
        LOGGER.exception("Reprise impossible")
        return 1
    finally:
        storage.close()

    if counts.skipped:
        LOGGER.info(
            "Historique deja en base pour %d site(s), ignore(s): %s",
            len(counts.skipped),
            ", ".join(counts.skipped),
        )
    LOGGER.info(
        "Reprise terminee: %d mesure(s) sur %d site(s)", counts.inserted, len(counts.backfilled)
    )

    if counts.failed:
        # Sortie en echec, sinon une reprise partielle passe pour une reussite.
        # Rien n est perdu pour autant : ces sites n ont laisse aucune ligne, le
        # demarrage suivant les reprend sans que personne ait a intervenir.
        LOGGER.error(
            "Reprise incomplete, %d site(s) en echec: %s. Repris au prochain demarrage.",
            len(counts.failed),
            ", ".join(counts.failed),
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
