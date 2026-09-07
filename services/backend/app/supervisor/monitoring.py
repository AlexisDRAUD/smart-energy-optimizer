"""Mesurer l erreur du modele en production, sans rien decider.

La comparaison prediction / realite est deja faite ligne a ligne : l API note
chaque prediction quand la mesure reelle arrive (`actual_kwh`), et PostgreSQL
calcule `absolute_error`. Le moniteur ne fait que lire `predictions` et
moyenner cette colonne sur une fenetre glissante, par site.

Seules les predictions de la version en production comptent, celle de la
derniere prediction emise pour le site : juste apres une promotion, les erreurs
de l ancien modele ne doivent pas juger le nouveau.

L horloge et l acces a la base sont injectes : les tests n attendent rien et ne
dependent d aucune heure reelle.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.contract import as_utc, utc_now
from app.db.models.prediction import Prediction

FENETRE_DECISION = timedelta(days=7)
FENETRE_ALERTE = timedelta(hours=24)


@dataclass(frozen=True)
class RapportSite:
    """Ce que le moniteur sait d un site a un instant donne."""

    site_id: str
    # Version de modele de la derniere prediction emise. None tant qu aucune
    # prediction n existe pour le site.
    version_en_production: str | None
    # MAE des predictions notees de cette version, sur chaque fenetre. None
    # quand aucune prediction notee ne tombe dans la fenetre.
    mae_decision: float | None
    mae_alerte: float | None
    notees_decision: int
    notees_alerte: int
    # Instant de la premiere prediction notee de la version en production,
    # toutes fenetres confondues. Sert a la regle "au moins 24 h de donnees
    # depuis la promotion".
    premiere_notation: datetime | None


class Moniteur:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        horloge: Callable[[], datetime] = utc_now,
        fenetre_decision: timedelta = FENETRE_DECISION,
        fenetre_alerte: timedelta = FENETRE_ALERTE,
    ):
        self.session_factory = session_factory
        self.horloge = horloge
        self.fenetre_decision = fenetre_decision
        self.fenetre_alerte = fenetre_alerte

    def mesurer(self, site_id: str) -> RapportSite:
        maintenant = self.horloge()
        with self.session_factory() as db:
            version = _version_en_production(db, site_id)
            if version is None:
                return RapportSite(site_id, None, None, None, 0, 0, None)

            mae_decision, notees_decision = _mae(
                db, site_id, version, maintenant - self.fenetre_decision, maintenant
            )
            mae_alerte, notees_alerte = _mae(
                db, site_id, version, maintenant - self.fenetre_alerte, maintenant
            )
            premiere = _premiere_notation(db, site_id, version)

        return RapportSite(
            site_id=site_id,
            version_en_production=version,
            mae_decision=mae_decision,
            mae_alerte=mae_alerte,
            notees_decision=notees_decision,
            notees_alerte=notees_alerte,
            premiere_notation=premiere,
        )


def _version_en_production(db: Session, site_id: str) -> str | None:
    return db.scalar(
        select(Prediction.model_version)
        .where(Prediction.site_id == site_id)
        .order_by(Prediction.predicted_at.desc(), Prediction.id.desc())
        .limit(1)
    )


def _mae(
    db: Session, site_id: str, version: str, debut: datetime, fin: datetime
) -> tuple[float | None, int]:
    """Moyenne de absolute_error sur [debut, fin], predictions notees seulement."""
    moyenne, nombre = db.execute(
        select(func.avg(Prediction.absolute_error), func.count()).where(
            Prediction.site_id == site_id,
            Prediction.model_version == version,
            Prediction.actual_kwh.is_not(None),
            Prediction.target_at >= debut,
            Prediction.target_at <= fin,
        )
    ).one()
    return (None if moyenne is None else float(moyenne), int(nombre))


def _premiere_notation(db: Session, site_id: str, version: str) -> datetime | None:
    premiere = db.scalar(
        select(func.min(Prediction.target_at)).where(
            Prediction.site_id == site_id,
            Prediction.model_version == version,
            Prediction.actual_kwh.is_not(None),
        )
    )
    return None if premiere is None else as_utc(premiere)
