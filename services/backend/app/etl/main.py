"""Boucle de transformation : du brut de raw_readings vers readings.

L ETL avance par fenetre de reception. Chaque passage repart de la borne de son
dernier passage reussi, moins un recouvrement, et lit tout ce qui est arrive
depuis. Rien n est ecrit sur le brut pour suivre ce qui a ete traite : la table
raw_readings reste en insertion seule, et l ETL reste rejouable a volonte.

Relire une mesure deja chargee ne produit rien, la cle unique de readings
absorbe le doublon. La justesse ne depend donc pas de la fenetre, seule la
quantite de travail en depend.
"""

import argparse
import logging
import time
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.quality import EtlRun
from app.db.session import SessionLocal
from app.etl.extract import (
    extract_from_raw_readings,
    extract_latest_sensors,
    extract_latest_sites,
)
from app.etl.impute import refresh_profiles, repair_readings, repair_window_start
from app.etl.load import load_readings, load_sensor_status, load_sites
from app.etl.quality import compute_daily_quality, days_touched
from app.etl.transform import transform_readings

LOGGER = logging.getLogger(__name__)

# Borne basse du premier passage, quand aucun passage reussi n existe encore.
# Assez ancienne pour couvrir n importe quelle reprise d historique.
DEBUT_DES_TEMPS = datetime(1970, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class PassCounts:
    """Ce qu un passage a lu et ecrit."""

    read: int = 0
    written: int = 0
    rejected: int = 0
    imputed: int = 0


def compute_window(db: Session, since: datetime | None) -> tuple[datetime, datetime]:
    """Rend la fenetre de reception a traiter.

    La borne basse vient du dernier passage *reussi*. Un passage en echec ne
    fait donc pas avancer la fenetre : ce qu il n a pas pu traiter sera repris
    au passage suivant, sans intervention.
    """
    end = datetime.now(UTC)
    if since is not None:
        return since, end

    last_success = db.scalar(
        select(EtlRun.window_end)
        .where(EtlRun.status == "ok")
        .order_by(EtlRun.window_end.desc())
        .limit(1)
    )
    if last_success is None:
        return DEBUT_DES_TEMPS, end
    return last_success - timedelta(minutes=settings.etl_window_overlap_minutes), end


def load_site_directory(db: Session) -> None:
    """Met le referentiel des sites a jour depuis le dernier instantane brut."""
    sites = extract_latest_sites(db)
    if not sites:
        LOGGER.info("Aucun instantane de sites en base, referentiel inchange")
        return
    LOGGER.info("Referentiel: %d site(s) a jour", load_sites(db, sites))


def load_sensor_directory(db: Session) -> None:
    """Historise l etat des capteurs depuis le dernier instantane brut."""
    snapshot = extract_latest_sensors(db)
    if snapshot is None:
        LOGGER.info("Aucun instantane de capteurs en base, historique inchange")
        return
    inserted = load_sensor_status(db, snapshot.received_at, snapshot.payload)
    LOGGER.info("Capteurs: %d observation(s) ajoutee(s)", inserted)


def transform_window(
    db: Session, window_start: datetime, window_end: datetime
) -> tuple[PassCounts, set[date]]:
    """Transforme la fenetre, lot par lot.

    Rend les compteurs du passage et les jours de mesure qu il a touches. Ces
    jours se lisent sur measured_at, pas sur la fenetre : celle-ci porte sur la
    reception, et une reprise d historique ecrit des mesures bien plus
    anciennes que le moment ou elles sont arrivees.
    """
    read = written = rejected = 0
    after_id = 0
    days: set[date] = set()

    while True:
        rows = extract_from_raw_readings(
            db, window_start, window_end, after_id, settings.etl_batch_size
        )
        if not rows:
            break

        transformed = transform_readings([row.payload for row in rows])
        loaded = load_readings(db, transformed.readings)

        read += len(rows)
        written += loaded.inserted_count
        rejected += transformed.rejected_count
        days.update(reading.timestamp.astimezone(UTC).date() for reading in transformed.readings)
        after_id = rows[-1].id

        if len(rows) < settings.etl_batch_size:
            break

    return PassCounts(read=read, written=written, rejected=rejected), days


def record_run(
    db: Session,
    started_at: datetime,
    window_start: datetime,
    window_end: datetime,
    counts: PassCounts,
    status: str,
    error_message: str | None = None,
) -> None:
    """Ecrit la trace du passage dans etl_runs.

    C est cette table qui porte l avancement de l ETL, et c est elle que le
    bandeau "derniere synchro" du dashboard lit.
    """
    db.add(
        EtlRun(
            started_at=started_at,
            finished_at=datetime.now(UTC),
            window_start=window_start,
            window_end=window_end,
            rows_read=counts.read,
            rows_written=counts.written,
            rows_imputed=counts.imputed,
            status=status,
            error_message=error_message,
        )
    )
    db.commit()


def run_once(since: datetime | None = None) -> int:
    """Execute un passage complet. Rend 0 si tout s est bien passe, 1 sinon."""
    started_at = datetime.now(UTC)
    try:
        with SessionLocal() as db:
            window_start, window_end = compute_window(db, since)
            load_site_directory(db)
            load_sensor_directory(db)
            counts, days = transform_window(db, window_start, window_end)
            # La reparation vient apres le chargement : une valeur nulle se
            # repare des que la mesure suivante est en base, donc au passage qui
            # vient de l ecrire.
            refresh_profiles(db)
            imputed = repair_readings(db, since)
            counts = replace(counts, imputed=imputed)
            # Le resume quotidien vient apres la reparation : il compte ce que
            # le chargement et la reparation ont laisse en base. Aux jours
            # charges s ajoutent ceux de la fenetre de reparation, qui a pu
            # remplir des valeurs sans qu aucune mesure nouvelle n arrive.
            days |= days_touched(repair_window_start(since, window_end), window_end)
            compute_daily_quality(db, days)
            record_run(db, started_at, window_start, window_end, counts, "ok")
    # Large volontairement : un passage rate ne doit ni tuer la boucle ni
    # laisser la trace de l echec de cote.
    except Exception as error:
        LOGGER.exception("Passage ETL en echec")
        _record_failure(started_at, error)
        return 1

    LOGGER.info(
        "Passage termine: fenetre %s -> %s, lues=%d ecrites=%d rejetees=%d reparees=%d",
        window_start.isoformat(timespec="seconds"),
        window_end.isoformat(timespec="seconds"),
        counts.read,
        counts.written,
        counts.rejected,
        counts.imputed,
    )
    return 0


def _record_failure(started_at: datetime, error: Exception) -> None:
    """Trace l echec dans etl_runs, sur une session neuve.

    La session du passage peut etre inutilisable apres l erreur. La fenetre est
    reduite a un instant : un passage en echec n a traite aucune fenetre, et son
    statut l empeche de toute facon de servir de borne au passage suivant.
    """
    try:
        with SessionLocal() as db:
            record_run(
                db,
                started_at,
                started_at,
                started_at,
                PassCounts(),
                "failed",
                error_message=str(error)[:500],
            )
    # La base est peut-etre injoignable : ne pas masquer l erreur d origine.
    except Exception:
        LOGGER.exception("Impossible d enregistrer l echec du passage")


def run_loop() -> int:
    """Boucle sans fin, un passage toutes les ETL_INTERVAL_SECONDS.

    Un passage en echec est journalise puis oublie : la boucle continue et
    reprendra le meme travail au tour suivant, puisque la fenetre n a pas avance.
    """
    LOGGER.info(
        "ETL demarre, un passage toutes les %d s, recouvrement de %d min",
        settings.etl_interval_seconds,
        settings.etl_window_overlap_minutes,
    )
    while True:
        run_once()
        time.sleep(settings.etl_interval_seconds)


def _parse_since(value: str) -> datetime:
    """Lit une date ISO en ligne de commande et la ramene en temps universel."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ETL des mesures EnerVision")
    parser.add_argument(
        "--once",
        action="store_true",
        help="execute un seul passage puis s arrete, au lieu de boucler",
    )
    parser.add_argument(
        "--since",
        type=_parse_since,
        metavar="DATE_ISO",
        help=(
            "force le debut de la fenetre, pour rejouer une periode. "
            "Exemple: --once --since 2026-09-01T00:00:00. "
            "Sans effet sur le brut, et sans doublon dans readings."
        ),
    )
    return parser


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    arguments = build_parser().parse_args()

    if arguments.since is not None and not arguments.once:
        build_parser().error("--since ne s utilise qu avec --once")

    if arguments.once:
        return run_once(arguments.since)
    return run_loop()


if __name__ == "__main__":
    raise SystemExit(main())
