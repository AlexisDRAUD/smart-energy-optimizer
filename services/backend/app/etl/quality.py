"""Agregat quotidien de la qualite des donnees, etage 2.

Un resume par site et par jour dans data_quality_daily, ecrit a la fin de
chaque passage pour les seuls jours que ce passage a touches. C est cette
table que lit la page "Qualite des donnees" : sans elle, elle affiche zero
partout alors que les mesures sont bien en base.

Le calcul est un denombrement de readings, il ne depend d aucun etat. Repasser
sur un jour deja resume recrit exactement les memes chiffres, un passage
rejoue ne fausse donc rien.
"""

import logging
from collections.abc import Iterable
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models.quality import DataQualityDaily
from app.db.models.reading import Reading
from app.db.models.site import Site

LOGGER = logging.getLogger(__name__)

# Une mesure par minute, c est la cadence de la source.
MINUTES_PER_DAY = 24 * 60


def days_touched(start: datetime, end: datetime) -> set[date]:
    """Rend les jours universels couverts par l intervalle, bornes comprises."""
    first = min(start, end).astimezone(UTC).date()
    last = max(start, end).astimezone(UTC).date()
    return {first + timedelta(days=offset) for offset in range((last - first).days + 1)}


def expected_points(day: date, now: datetime) -> int:
    """Nombre de mesures attendues pour ce jour a l instant du calcul.

    Un jour revolu en attend 1440, une par minute. Le jour en cours n en attend
    que les minutes deja ecoulees : en attendre 1440 des minuit ferait passer
    la fin de la journee, qui n a pas encore eu lieu, pour un trou de collecte,
    et le dashboard signalerait des donnees incompletes jusqu au soir.
    """
    today = now.astimezone(UTC).date()
    if day < today:
        return MINUTES_PER_DAY
    if day > today:
        return 0
    moment = now.astimezone(UTC)
    return min(moment.hour * 60 + moment.minute + 1, MINUTES_PER_DAY)


def _counts_for_day(db: Session, day: date) -> dict[str, tuple[int, int, int]]:
    """Denombre, par site, ce que readings porte pour ce jour."""
    day_start = datetime.combine(day, time.min, tzinfo=UTC)
    rows = db.execute(
        select(
            Reading.site_id,
            func.count().label("received"),
            # La valeur brute est ce que la source a repondu : nulle, la mesure
            # est arrivee sans consommation. consumption_kwh ne dirait pas la
            # meme chose, la reparation l a peut-etre deja remplie.
            func.count().filter(Reading.consumption_kwh_raw.is_(None)).label("nulls"),
            func.count().filter(Reading.is_imputed.is_(True)).label("imputed"),
        )
        .where(
            Reading.measured_at >= day_start,
            Reading.measured_at < day_start + timedelta(days=1),
        )
        .group_by(Reading.site_id)
    ).all()
    return {row.site_id: (row.received, row.nulls, row.imputed) for row in rows}


def compute_daily_quality(db: Session, days: Iterable[date], now: datetime | None = None) -> int:
    """Recalcule le resume quotidien des jours donnes. Rend le nombre de lignes.

    Un site du referentiel qui n a rien remonte de la journee recoit quand meme
    sa ligne, a zero recu : c est exactement le trou de collecte, et il ne se
    lit nulle part ailleurs. Un site absent du referentiel mais present dans
    les mesures est resume lui aussi, readings n ayant pas de cle etrangere
    vers sites.
    """
    moment = now or datetime.now(UTC)
    known_sites = set(db.scalars(select(Site.site_id)))

    values = []
    for day in sorted(set(days)):
        counts = _counts_for_day(db, day)
        expected = expected_points(day, moment)
        for site_id in sorted(known_sites | counts.keys()):
            received, nulls, imputed = counts.get(site_id, (0, 0, 0))
            values.append(
                {
                    "site_id": site_id,
                    "day": day,
                    "expected_points": expected,
                    "received_points": received,
                    # Jamais negatif : le jour en cours peut recevoir la minute
                    # que le calcul n a pas encore comptee comme ecoulee.
                    "missing_points": max(expected - received, 0),
                    "null_points": nulls,
                    "imputed_points": imputed,
                    "computed_at": moment,
                }
            )

    if not values:
        return 0

    statement = insert(DataQualityDaily).values(values)
    statement = statement.on_conflict_do_update(
        constraint="uq_data_quality_daily_site_day",
        set_={
            "expected_points": statement.excluded.expected_points,
            "received_points": statement.excluded.received_points,
            "missing_points": statement.excluded.missing_points,
            "null_points": statement.excluded.null_points,
            "imputed_points": statement.excluded.imputed_points,
            "computed_at": statement.excluded.computed_at,
        },
    )

    try:
        db.execute(statement)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    LOGGER.info("Qualite: %d resume(s) quotidien(s) a jour", len(values))
    return len(values)
