"""Reparation des valeurs nulles de consommation, etage 2.

Applique la strategie de l ADR du 04/09. Deux mecanismes distincts :

1. le profil de chaque site, decide par le backtest hors ligne et range dans
   sites.imputation_profile. Il choisit la methode de reparation ;
2. la reparation elle-meme, qui repasse a chaque passage sur les dernieres
   minutes de readings.

Trois regles tiennent tout le reste :

- le calcul part toujours de consumption_kwh_raw, jamais de consumption_kwh.
  Repasser cent fois sur la meme fenetre donne exactement le meme resultat ;
- l ecriture porte WHERE consumption_kwh_raw IS NULL, donc une valeur reelle
  n est jamais ecrasee ;
- un trou n est repare que s il est referme, encadre par deux valeurs reelles
  a la cadence exacte d une minute. Un trou encore ouvert reste ouvert : le
  combler serait de l extrapolation.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.analysis.imputation_backtest import (
    BacktestConfig,
    ConsumptionObservation,
    compare_imputation_methods,
)
from app.config import settings

LOGGER = logging.getLogger(__name__)

CADENCE = timedelta(minutes=1)
# Profondeur d historique sur laquelle le profil est decide. Sept jours, comme
# la reprise : c est la fenetre sur laquelle l ADR a ete valide.
PROFILE_LOOKBACK_DAYS = 7
# Marge chargee avant la fenetre de reparation, pour trouver la valeur reelle
# qui precede un trou commence juste avant la fenetre.
ANCHOR_MARGIN_MINUTES = 10

INTERPOLATION = "interpolation"
REPORT = "report"


@dataclass(frozen=True)
class Observation:
    """Une mesure de la fenetre de reparation."""

    measured_at: datetime
    consumption_kwh_raw: float | None
    null_reasons: tuple[str, ...]

    @property
    def is_real(self) -> bool:
        """Une valeur exploitable comme point d ancrage.

        Meme definition que le backtest : une perte reseau invalide la mesure
        meme si un chiffre l accompagne.
        """
        return self.consumption_kwh_raw is not None and "network_loss" not in self.null_reasons


def refresh_profiles(db: Session, now: datetime | None = None) -> int:
    """Recalcule le profil des sites dont la decision est absente ou perimee.

    Rend le nombre de sites reclasses. Le backtest tourne sur plusieurs dizaines
    de milliers de points par site : il est volontairement rare, une fois par
    IMPUTATION_PROFILE_REFRESH_HOURS.
    """
    computed_at = now or datetime.now(UTC)
    cutoff = computed_at - timedelta(hours=settings.imputation_profile_refresh_hours)

    site_ids = list(
        db.execute(
            text(
                "SELECT site_id FROM sites "
                "WHERE imputation_profile_at IS NULL OR imputation_profile_at < :cutoff "
                "ORDER BY site_id"
            ),
            {"cutoff": cutoff},
        ).scalars()
    )
    if not site_ids:
        return 0

    window_start = computed_at - timedelta(days=PROFILE_LOOKBACK_DAYS)
    rows = db.execute(
        text(
            "SELECT site_id, measured_at, consumption_kwh_raw, null_reasons FROM readings "
            "WHERE site_id = ANY(:site_ids) AND measured_at >= :window_start "
            "ORDER BY site_id, measured_at"
        ),
        {"site_ids": site_ids, "window_start": window_start},
    ).all()

    observations = [
        ConsumptionObservation(
            site_id=row.site_id,
            measured_at=row.measured_at,
            consumption_kwh_raw=row.consumption_kwh_raw,
            null_reasons=tuple(row.null_reasons or ()),
        )
        for row in rows
    ]

    results = {backtest.site_id: backtest for backtest in compare_imputation_methods(observations)}
    for site_id in site_ids:
        result = results.get(site_id)
        # Un site sans historique exploitable reste unknown, donc non impute.
        profile = result.profile if result else "unknown"
        reason = result.decision_reason if result else "no_history"
        db.execute(
            text(
                "UPDATE sites SET imputation_profile = :profile, "
                "imputation_profile_at = :computed_at "
                "WHERE site_id = :site_id"
            ),
            {"profile": profile, "computed_at": computed_at, "site_id": site_id},
        )
        LOGGER.info("Profil de %s: %s (%s)", site_id, profile, reason)

    db.commit()
    return len(site_ids)


def _fill_gap(
    window: Sequence[Observation], start: int, end: int, profile: str
) -> list[tuple[datetime, float]]:
    """Rend les valeurs a ecrire pour le trou window[start:end], ou rien.

    *start* et *end* encadrent les valeurs nulles : window[start] et window[end]
    sont les deux valeurs reelles d ancrage.
    """
    before = window[start]
    after = window[end]
    duration = after.measured_at - before.measured_at

    # Le trou doit etre referme a la cadence exacte : une minute manquante dans
    # la suite est un trou de collecte, pas une valeur nulle, et on ne
    # l enjambe pas.
    missing_count = end - start - 1
    if duration != CADENCE * (missing_count + 1):
        return []
    if missing_count > BacktestConfig().maximum_gap_minutes:
        return []

    value_before = before.consumption_kwh_raw
    value_after = after.consumption_kwh_raw
    if value_before is None or value_after is None:
        return []

    values = []
    for index in range(start + 1, end):
        gap = window[index]
        if profile == REPORT:
            values.append((gap.measured_at, value_before))
        else:
            fraction = (gap.measured_at - before.measured_at) / duration
            values.append((gap.measured_at, value_before + fraction * (value_after - value_before)))
    return values


def _repair_one_site(db: Session, site_id: str, profile: str, window_start: datetime) -> int:
    """Repare les trous refermes d un site. Rend le nombre de lignes ecrites."""
    method = INTERPOLATION if profile == "variable" else REPORT

    rows = db.execute(
        text(
            "SELECT measured_at, consumption_kwh_raw, null_reasons FROM readings "
            "WHERE site_id = :site_id AND measured_at >= :window_start "
            "ORDER BY measured_at"
        ),
        {
            "site_id": site_id,
            "window_start": window_start - timedelta(minutes=ANCHOR_MARGIN_MINUTES),
        },
    ).all()

    window = [
        Observation(
            measured_at=row.measured_at,
            consumption_kwh_raw=row.consumption_kwh_raw,
            null_reasons=tuple(row.null_reasons or ()),
        )
        for row in rows
    ]

    to_write: list[tuple[datetime, float]] = []
    last_real = None
    for index, observation in enumerate(window):
        if not observation.is_real:
            continue
        if last_real is not None and index > last_real + 1:
            to_write.extend(_fill_gap(window, last_real, index, method))
        last_real = index

    if not to_write:
        return 0

    result = db.execute(
        text(
            "UPDATE readings SET consumption_kwh = :value, is_imputed = true, "
            "imputation_method = :method "
            # Deux gardes. La premiere rend l operation sure : une valeur
            # reelle n est jamais touchee. La seconde evite de reecrire une
            # ligne deja reparee a l identique, ce qui epargne l ecriture et
            # rend le compte rendu honnete : rows_imputed ne compte que les
            # reparations reelles, pas les passages.
            "WHERE site_id = :site_id AND measured_at = :instant "
            "AND consumption_kwh_raw IS NULL "
            "AND (is_imputed IS NOT TRUE OR consumption_kwh IS DISTINCT FROM :value)"
        ),
        [
            {"value": round(value, 3), "method": method, "site_id": site_id, "instant": instant}
            for instant, value in to_write
        ],
    )
    db.commit()
    return result.rowcount


def repair_window_start(since: datetime | None = None, now: datetime | None = None) -> datetime:
    """Debut de la fenetre de reparation d un passage.

    Expose a part parce que l appelant en a besoin lui aussi : ce sont les
    jours de cette fenetre que le resume quotidien doit recalculer, une
    reparation changeant le compte des valeurs imputees.
    """
    if since is not None:
        return since
    return (now or datetime.now(UTC)) - timedelta(minutes=settings.imputation_window_minutes)


def repair_readings(db: Session, since: datetime | None = None) -> int:
    """Repare les valeurs nulles de tous les sites au profil connu.

    Rend le nombre de lignes ecrites. Un site au profil unknown ou absent n est
    pas repare : c est ce qui protege un historique douteux sans qu aucun
    identifiant de site figure dans le code.
    """
    window_start = repair_window_start(since)

    sites = db.execute(
        text(
            "SELECT site_id, imputation_profile FROM sites "
            "WHERE imputation_profile IN ('variable', 'stable') ORDER BY site_id"
        )
    ).all()

    total = 0
    for site in sites:
        total += _repair_one_site(db, site.site_id, site.imputation_profile, window_start)
    return total
