"""PostgreSQL loading adapter for validated energy readings."""

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models.quality import SensorStatus
from app.db.models.reading import Reading
from app.db.models.site import Site
from app.etl.transform import EnergyReading

LOGGER = logging.getLogger(__name__)

# Champs qu un site doit porter pour entrer dans le referentiel. Ils sont tous
# obligatoires en base, un site incomplet ne peut donc pas etre insere.
SITE_FIELDS = ("site_id", "site_type", "site_name", "location", "capacity_kw", "status")

# Valeurs admises par le schema. Une valeur inconnue signale un changement de
# la source : la ligne est ecartee avec un avertissement plutot que de faire
# echouer le lot entier sur une contrainte.
SENSOR_NAMES = ("consumption", "electrical", "temperature", "humidity", "network")
SENSOR_STATUSES = ("ok", "failing")


@dataclass(frozen=True)
class LoadResult:
    inserted_count: int
    skipped_count: int


def to_minute(instant: datetime) -> datetime:
    """Ramene un horodatage a la minute.

    Les deux endpoints de la source ne rendent pas la meme forme : l historique
    donne des minutes pleines, l instantane rend l heure courante a la
    microseconde. Sans alignement, les deux origines forment deux series
    decalees, la cadence n est jamais exactement d une minute, et tout ce qui en
    depend cesse de fonctionner : la reparation des valeurs nulles, le backtest
    de l ADR, et les 1440 points attendus par jour de data_quality_daily.

    Le brut garde l horodatage exact : rien n est perdu, tout reste rejouable.
    """
    return instant.replace(second=0, microsecond=0)


def load_readings(db: Session, readings: Sequence[EnergyReading]) -> LoadResult:
    """Insert readings atomically and ignore only duplicate measurement keys."""
    if not readings:
        return LoadResult(inserted_count=0, skipped_count=0)

    ingested_at = datetime.now(UTC)
    values = [
        {
            "site_id": reading.site_id,
            "measured_at": to_minute(reading.timestamp),
            "consumption_kwh_raw": reading.consumption_kwh,
            "consumption_kwh": reading.consumption_kwh,
            "is_imputed": False,
            "imputation_method": None,
            "temperature_celsius": reading.temperature_celsius,
            "humidity_percent": reading.humidity_percent,
            "data_quality": reading.data_quality,
            "null_reasons": reading.null_reasons,
            "ingested_at": ingested_at,
        }
        for reading in readings
    ]
    statement = (
        insert(Reading)
        .values(values)
        .on_conflict_do_nothing(constraint="uq_readings_site_measured")
        .returning(Reading.site_id)
    )

    try:
        inserted_count = len(db.execute(statement).scalars().all())
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    return LoadResult(
        inserted_count=inserted_count,
        skipped_count=len(readings) - inserted_count,
    )


def load_sites(
    db: Session, sites_payload: Sequence[Mapping[str, Any]], logger: logging.Logger | None = None
) -> int:
    """Met a jour le referentiel des sites depuis un instantane brut.

    Mise a jour ou insertion sur site_id : relancer ne cree jamais de doublon.
    first_seen_at n est pose qu a l insertion, last_seen_at a chaque passage,
    ce qui donne la date de premiere et de derniere apparition d un site.

    Un site auquel il manque un champ obligatoire est ignore avec un
    avertissement plutot que de faire echouer le passage : un site incomplet ne
    doit pas empecher les autres d arriver.
    """
    active_logger = logger or LOGGER
    now = datetime.now(UTC)
    values = []
    for site in sites_payload:
        missing = [field for field in SITE_FIELDS if site.get(field) is None]
        if missing:
            active_logger.warning(
                "Site ignore, champs manquants %s: %s", missing, site.get("site_id", "sans id")
            )
            continue
        values.append(
            {
                "site_id": site["site_id"],
                "site_type": site["site_type"],
                "site_name": site["site_name"],
                "location": site["location"],
                "capacity_kw": site["capacity_kw"],
                "status": site["status"],
                "first_seen_at": now,
                "last_seen_at": now,
            }
        )

    if not values:
        return 0

    statement = insert(Site).values(values)
    statement = statement.on_conflict_do_update(
        index_elements=["site_id"],
        set_={
            "site_type": statement.excluded.site_type,
            "site_name": statement.excluded.site_name,
            "location": statement.excluded.location,
            "capacity_kw": statement.excluded.capacity_kw,
            "status": statement.excluded.status,
            "last_seen_at": statement.excluded.last_seen_at,
        },
    )

    try:
        db.execute(statement)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    return len(values)


def _parse_failing_until(value: Any) -> datetime | None:
    """Lit failing_until, que la source rend en ISO ou a nul."""
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def load_sensor_status(
    db: Session,
    observed_at: datetime,
    payload: Mapping[str, Any],
    logger: logging.Logger | None = None,
) -> int:
    """Historise l etat des capteurs depuis un instantane brut.

    observed_at est l horodatage de reception de l instantane, pas l heure du
    chargement : recharger le meme instantane produit exactement les memes
    lignes, que la cle unique (site, capteur, instant) ignore. Sans cela chaque
    passage de l ETL creerait un nouvel historique pour un etat inchange.
    """
    active_logger = logger or LOGGER
    values = []
    for site_id, site_state in payload.items():
        sensors = site_state.get("sensors") if isinstance(site_state, Mapping) else None
        if not isinstance(sensors, Mapping):
            active_logger.warning("Etat de capteurs illisible pour le site %s", site_id)
            continue
        for sensor, state in sensors.items():
            status = state.get("status") if isinstance(state, Mapping) else None
            if sensor not in SENSOR_NAMES or status not in SENSOR_STATUSES:
                active_logger.warning(
                    "Capteur ignore, valeur hors contrat: site=%s capteur=%s statut=%s",
                    site_id,
                    sensor,
                    status,
                )
                continue
            values.append(
                {
                    "site_id": site_id,
                    "sensor": sensor,
                    "observed_at": observed_at,
                    "status": status,
                    "failing_until": _parse_failing_until(state.get("failing_until")),
                }
            )

    if not values:
        return 0

    statement = (
        insert(SensorStatus)
        .values(values)
        .on_conflict_do_nothing(constraint="uq_sensor_status_site_sensor_observed")
        .returning(SensorStatus.site_id)
    )

    try:
        inserted = len(db.execute(statement).scalars().all())
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    return inserted
