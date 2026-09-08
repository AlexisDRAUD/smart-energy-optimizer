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
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx
from sqlalchemy import text

from app.collector.storage import PostgresStorage
from app.config import settings

LOGGER = logging.getLogger(__name__)

WINDOW_MINUTES = 1000  # 1000 points sur 1000 minutes = 1 point/minute
TIMEOUT_SECONDS = 60

# Delais entre deux tentatives sur une meme fenetre, en secondes. Une reprise de
# deux ans represente un millier de fenetres par site : sans nouvelle tentative,
# une seule coupure reseau passagere suffit a perdre tout le travail du site.
RETRY_DELAYS = (2.0, 5.0)

# Une ligne de journal toutes les N fenetres. Un run de plusieurs dizaines de
# minutes sans trace ne se distingue pas d un run bloque.
PROGRESS_EVERY_WINDOWS = 50


class Backfill:
    """Reprise de l historique d un seul site."""

    def __init__(
        self,
        storage,
        api_client,
        site_id: str,
        days: int | None = None,
        retry_delays: Sequence[float] = RETRY_DELAYS,
    ):
        self.storage = storage
        self.api_client = api_client
        self.site_id = site_id
        self.days = settings.backfill_days if days is None else days
        self.retry_delays = tuple(retry_delays)

    def run(self) -> int:
        """Rend le nombre de mesures reellement inserees.

        Chaque fenetre est ecrite des qu elle est lue, et non conservee jusqu a
        la fin. Sur deux ans, tout garder en memoire represente environ un
        million d entrees par site, de l ordre du gigaoctet : le conteneur se
        fait tuer avant d avoir ecrit la moindre ligne. En ecrivant au fil de
        l eau, la memoire ne depend plus de la profondeur demandee.

        Ce qui a ete lu est garde, meme si une fenetre suivante echoue. Rien ne
        rend la fenetre 151 dependante de la 150, et jeter cent cinquante
        fenetres deja obtenues pour une coupure de deux secondes serait du
        gachis. C est la garde de already_backfilled_sites qui rattrape le
        manque : elle mesure jusqu ou remonte l historique, donc un site
        incomplet est repris au passage suivant.

        Les appels restent hors de toute transaction longue : chaque fenetre a
        la sienne, tenir une transaction ouverte le temps d un millier d
        allers-retours reseau bloquerait le nettoyage de la table pour rien.
        """
        end = datetime.now().replace(second=0, microsecond=0)
        start = end - timedelta(days=self.days)

        inserted_count = 0
        windows_read = 0
        cursor = start
        try:
            while cursor < end:
                window_end = min(cursor + timedelta(minutes=WINDOW_MINUTES), end)
                limit = int((window_end - cursor).total_seconds() / 60)
                measurements = self._read_window(cursor, window_end, limit)
                inserted_count += self.storage.store_raw_many(
                    "api_backfill", [json.dumps(measurement) for measurement in measurements]
                )
                cursor = window_end
                windows_read += 1
                if windows_read % PROGRESS_EVERY_WINDOWS == 0:
                    LOGGER.info(
                        "Site %s: %d fenetre(s) lues, %d mesure(s) ecrites, jusqu au %s",
                        self.site_id,
                        windows_read,
                        inserted_count,
                        window_end.isoformat(timespec="minutes"),
                    )
        except Exception:
            LOGGER.error(
                "Site %s: reprise interrompue apres %d fenetre(s), %d mesure(s) deja ecrites",
                self.site_id,
                windows_read,
                inserted_count,
            )
            raise

        LOGGER.info(
            "Site %s: %d mesure(s) reprises sur %d jour(s)", self.site_id, inserted_count, self.days
        )
        return inserted_count

    def _read_window(self, start_time: datetime, end_time: datetime, limit: int):
        """Lit une fenetre, en retentant selon retry_delays avant d abandonner.

        L abandon efface tout le site, donc mieux vaut insister un peu ici que
        de refaire un millier de fenetres pour une coupure de deux secondes.
        """
        attempts = len(self.retry_delays) + 1
        for attempt in range(1, attempts + 1):
            try:
                return self.api_client(self.site_id, start_time, end_time, limit)
            except Exception:
                if attempt == attempts:
                    raise
                delay = self.retry_delays[attempt - 1]
                LOGGER.warning(
                    "Site %s: fenetre %s en echec (tentative %d/%d), nouvel essai dans %.0fs",
                    self.site_id,
                    start_time.isoformat(timespec="minutes"),
                    attempt,
                    attempts,
                    delay,
                )
                time.sleep(delay)


def already_backfilled_sites(storage, days: int | None = None) -> set[str]:
    """Les sites dont l historique remonte deja assez loin pour la profondeur demandee.

    La garde mesure une couverture, pas une presence. Un site n est considere
    comme repris que si sa plus ancienne mesure atteint la profondeur demandee.
    Deux consequences voulues.

    Un site interrompu en cours de reprise garde ce qu il a lu, mais reste
    incomplet, donc le passage suivant va chercher ce qui manque au lieu de le
    sauter pour toujours.

    Et augmenter BACKFILL_DAYS reprend le complement. Une pile demarree une
    fois avec sept jours ne bloque pas une reprise a deux ans : les sites ne
    couvrent pas la nouvelle profondeur, ils sont redemandes. Avec une garde
    fondee sur la simple presence de lignes, ils auraient tous ete sautes en
    silence.

    Le prix a connaitre : l endpoint historique regenere les donnees a chaque
    appel, donc completer un site melange deux generations dans sa serie, avec
    une discontinuite au point de reprise. C est moins couteux que de perdre
    l historique deja obtenu, ou de croire complet un site qui ne l est pas.

    Seules les lignes de source api_backfill comptent. Le collecteur ecrit lui
    aussi dans raw_readings, et compter ses lignes ferait passer pour repris un
    site dont on n a que les dernieres minutes.
    """
    depth = settings.backfill_days if days is None else days
    earliest_needed = (
        datetime.now().replace(second=0, microsecond=0) - timedelta(days=depth)
    ).isoformat(timespec="seconds")
    with storage.engine.connect() as conn:
        return set(
            conn.execute(
                text(
                    "SELECT site_id FROM raw_readings "
                    "WHERE source = 'api_backfill' "
                    "GROUP BY site_id "
                    "HAVING MIN(measured_at) <= :earliest"
                ),
                {"earliest": earliest_needed},
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
    api_client,
    site_ids: Sequence[str],
    days: int | None = None,
    force: bool = False,
    retry_delays: Sequence[float] = RETRY_DELAYS,
) -> BackfillCounts:
    """Reprend l historique des sites qui n ont pas encore le leur.

    Un site en erreur n arrete pas les autres : la source peut refuser un site
    et repondre pour les suivants, autant garder ce qu on peut. Il est nomme
    dans le compte rendu, et comme un site en echec ne laisse aucune ligne, le
    demarrage suivant le reprend de lui-meme.
    """
    depth = settings.backfill_days if days is None else days
    already_backfilled = set() if force else already_backfilled_sites(storage, depth)

    inserted = 0
    backfilled: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []
    for site_id in site_ids:
        if site_id in already_backfilled:
            skipped.append(site_id)
            continue
        try:
            inserted += Backfill(storage, api_client, site_id, depth, retry_delays).run()
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


def read_sites(client: httpx.Client) -> list[dict]:
    response = client.get("/api/v1/sites")
    response.raise_for_status()
    return response.json()


def real_api_client(client: httpx.Client):
    """Fabrique la fonction d appel attendue par Backfill."""

    def call(site_id, start_time, end_time, limit):
        response = client.get(
            "/api/v1/readings",
            params={
                "site_id": site_id,
                "start_time": start_time.isoformat(timespec="seconds"),
                "end_time": end_time.isoformat(timespec="seconds"),
                "limit": limit,
            },
        )
        response.raise_for_status()
        return response.json()

    return call


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
            sites = read_sites(client)
            # Le referentiel part en base des maintenant : sans lui l API repond
            # 404 sur tout jusqu au premier passage du collecteur.
            storage.store_snapshot("api_sites", json.dumps(sites))

            site_ids = arguments.sites or [site["site_id"] for site in sites]
            counts = run_backfill(
                storage, real_api_client(client), site_ids, arguments.days, arguments.force
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
