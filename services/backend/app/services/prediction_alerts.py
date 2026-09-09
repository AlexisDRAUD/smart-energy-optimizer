"""Alertes de prevision : detecter une hausse trop rapide de la consommation prevue.

Le worker de prevision (``model/predict.py``) ecrit une prevision par site a
l horizon configure. Une prevision nettement plus haute que le dernier releve
reel annonce une montee de charge : c est ce que cette regle transforme en
alerte, avant que la consommation ne soit constatee.

La pente est ramenee au pourcentage par heure pour rester comparable quel que
soit l horizon configure :

    pente = (prevu - reference) / reference * 100 * 60 / horizon_minutes

Elle est comparee au seuil ``prediction_alert_rise_percent_per_hour``. Plus la
pente depasse le seuil, plus la severite est elevee.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.alert import Alert

ALERT_TYPE = "forecast"

# Multiplicateurs du seuil de base, du plus grave au plus faible.
_SEVERITY_STEPS: tuple[tuple[float, str], ...] = (
    (3.0, "critical"),
    (2.0, "high"),
    (1.0, "medium"),
)


def rise_percent_per_hour(
    baseline_kwh: float, predicted_kwh: float, horizon_minutes: int
) -> float | None:
    """Vitesse de montee prevue, en pourcentage par heure.

    Renvoie ``None`` quand le calcul n a pas de sens : horizon nul, reference
    negative, ou reference trop faible pour qu un rapport soit significatif
    (une mesure proche de zero rend n importe quelle hausse enorme en relatif).
    """
    if horizon_minutes <= 0:
        return None
    if baseline_kwh < settings.prediction_alert_min_baseline_kwh:
        return None
    return (predicted_kwh - baseline_kwh) / baseline_kwh * 100 * 60 / horizon_minutes


def severity_for(slope_percent_per_hour: float) -> str | None:
    """Severite associee a une pente, ou ``None`` sous le seuil."""
    threshold = settings.prediction_alert_rise_percent_per_hour
    if threshold <= 0:
        return None
    for multiplier, severity in _SEVERITY_STEPS:
        if slope_percent_per_hour >= threshold * multiplier:
            return severity
    return None


def evaluate_prediction_rise(
    db: Session,
    *,
    site_id: str,
    baseline_kwh: float,
    predicted_kwh: float,
    horizon_minutes: int,
    detected_at: datetime,
) -> Alert | None:
    """Ajouter une alerte de prevision si la montee prevue depasse le seuil.

    L alerte est ajoutee a la session sans commit : l appelant valide la
    transaction avec les previsions du meme passage. Rien n est ecrit deux fois
    pour un meme site au meme instant.
    """
    slope = rise_percent_per_hour(baseline_kwh, predicted_kwh, horizon_minutes)
    if slope is None:
        return None
    severity = severity_for(slope)
    if severity is None:
        return None

    already_open = db.scalar(
        select(Alert.id).where(
            Alert.site_id == site_id,
            Alert.type == ALERT_TYPE,
            Alert.detected_at == detected_at,
        )
    )
    if already_open is not None:
        return None

    threshold_kwh = round(
        baseline_kwh
        * (1 + settings.prediction_alert_rise_percent_per_hour / 100 * horizon_minutes / 60),
        3,
    )
    alert = Alert(
        site_id=site_id,
        detected_at=detected_at,
        type=ALERT_TYPE,
        severity=severity,
        message=(
            f"Hausse prevue de {slope:.1f} %/h : "
            f"{predicted_kwh:.3f} kWh attendus dans {horizon_minutes} min "
            f"contre {baseline_kwh:.3f} kWh mesures."
        ),
        value=round(predicted_kwh, 3),
        threshold_value=threshold_kwh,
        status="open",
        origin="internal",
    )
    db.add(alert)
    return alert
