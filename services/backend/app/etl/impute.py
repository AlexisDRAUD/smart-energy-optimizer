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
    moment = now or datetime.now(UTC)
    limite = moment - timedelta(hours=settings.imputation_profile_refresh_hours)

    site_ids = list(
        db.execute(
            text(
                "SELECT site_id FROM sites "
                "WHERE imputation_profile_at IS NULL OR imputation_profile_at < :limite "
                "ORDER BY site_id"
            ),
            {"limite": limite},
        ).scalars()
    )
    if not site_ids:
        return 0

    depuis = moment - timedelta(days=PROFILE_LOOKBACK_DAYS)
    lignes = db.execute(
        text(
            "SELECT site_id, measured_at, consumption_kwh_raw, null_reasons FROM readings "
            "WHERE site_id = ANY(:site_ids) AND measured_at >= :depuis "
            "ORDER BY site_id, measured_at"
        ),
        {"site_ids": site_ids, "depuis": depuis},
    ).all()

    observations = [
        ConsumptionObservation(
            site_id=ligne.site_id,
            measured_at=ligne.measured_at,
            consumption_kwh_raw=ligne.consumption_kwh_raw,
            null_reasons=tuple(ligne.null_reasons or ()),
        )
        for ligne in lignes
    ]

    resultats = {r.site_id: r for r in compare_imputation_methods(observations)}
    for site_id in site_ids:
        resultat = resultats.get(site_id)
        # Un site sans historique exploitable reste unknown, donc non impute.
        profil = resultat.profile if resultat else "unknown"
        raison = resultat.decision_reason if resultat else "no_history"
        db.execute(
            text(
                "UPDATE sites SET imputation_profile = :profil, imputation_profile_at = :moment "
                "WHERE site_id = :site_id"
            ),
            {"profil": profil, "moment": moment, "site_id": site_id},
        )
        LOGGER.info("Profil de %s: %s (%s)", site_id, profil, raison)

    db.commit()
    return len(site_ids)


def _combler(
    fenetre: Sequence[Observation], debut: int, fin: int, profil: str
) -> list[tuple[datetime, float]]:
    """Rend les valeurs a ecrire pour le trou fenetre[debut:fin], ou rien.

    *debut* et *fin* encadrent les valeurs nulles : fenetre[debut] et
    fenetre[fin] sont les deux valeurs reelles d ancrage.
    """
    avant = fenetre[debut]
    apres = fenetre[fin]
    duree = apres.measured_at - avant.measured_at

    # Le trou doit etre referme a la cadence exacte : une minute manquante dans
    # la suite est un trou de collecte, pas une valeur nulle, et on ne
    # l enjambe pas.
    manquantes = fin - debut - 1
    if duree != CADENCE * (manquantes + 1):
        return []
    if manquantes > BacktestConfig().maximum_gap_minutes:
        return []

    valeur_avant = avant.consumption_kwh_raw
    valeur_apres = apres.consumption_kwh_raw
    if valeur_avant is None or valeur_apres is None:
        return []

    valeurs = []
    for index in range(debut + 1, fin):
        trou = fenetre[index]
        if profil == REPORT:
            valeurs.append((trou.measured_at, valeur_avant))
        else:
            fraction = (trou.measured_at - avant.measured_at) / duree
            valeurs.append(
                (trou.measured_at, valeur_avant + fraction * (valeur_apres - valeur_avant))
            )
    return valeurs


def _reparer_un_site(db: Session, site_id: str, profil: str, depuis: datetime) -> int:
    """Repare les trous refermes d un site. Rend le nombre de lignes ecrites."""
    methode = INTERPOLATION if profil == "variable" else REPORT

    lignes = db.execute(
        text(
            "SELECT measured_at, consumption_kwh_raw, null_reasons FROM readings "
            "WHERE site_id = :site_id AND measured_at >= :depuis "
            "ORDER BY measured_at"
        ),
        {"site_id": site_id, "depuis": depuis - timedelta(minutes=ANCHOR_MARGIN_MINUTES)},
    ).all()

    fenetre = [
        Observation(
            measured_at=ligne.measured_at,
            consumption_kwh_raw=ligne.consumption_kwh_raw,
            null_reasons=tuple(ligne.null_reasons or ()),
        )
        for ligne in lignes
    ]

    a_ecrire: list[tuple[datetime, float]] = []
    dernier_reel = None
    for index, observation in enumerate(fenetre):
        if not observation.is_real:
            continue
        if dernier_reel is not None and index > dernier_reel + 1:
            a_ecrire.extend(_combler(fenetre, dernier_reel, index, methode))
        dernier_reel = index

    if not a_ecrire:
        return 0

    resultat = db.execute(
        text(
            "UPDATE readings SET consumption_kwh = :valeur, is_imputed = true, "
            "imputation_method = :methode "
            # Deux gardes. La premiere rend l operation sure : une valeur
            # reelle n est jamais touchee. La seconde evite de reecrire une
            # ligne deja reparee a l identique, ce qui epargne l ecriture et
            # rend le compte rendu honnete : rows_imputed ne compte que les
            # reparations reelles, pas les passages.
            "WHERE site_id = :site_id AND measured_at = :instant "
            "AND consumption_kwh_raw IS NULL "
            "AND (is_imputed IS NOT TRUE OR consumption_kwh IS DISTINCT FROM :valeur)"
        ),
        [
            {"valeur": round(valeur, 3), "methode": methode, "site_id": site_id, "instant": instant}
            for instant, valeur in a_ecrire
        ],
    )
    db.commit()
    return resultat.rowcount


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
    depuis = repair_window_start(since)

    sites = db.execute(
        text(
            "SELECT site_id, imputation_profile FROM sites "
            "WHERE imputation_profile IN ('variable', 'stable') ORDER BY site_id"
        )
    ).all()

    total = 0
    for site in sites:
        total += _reparer_un_site(db, site.site_id, site.imputation_profile, depuis)
    return total
