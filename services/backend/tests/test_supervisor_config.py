"""Tests des reglages du superviseur : variables d environnement SUPERVISOR_*.

Chaque reglage a un defaut, se lit dans l environnement, et refuse les valeurs
qui n ont pas de sens (zero, negatif). Les durees sont exposees en timedelta
pour etre passees telles quelles au moniteur et a l ordonnanceur.
"""

from datetime import timedelta

import pytest
from app.supervisor.config import SupervisorSettings
from pydantic import ValidationError


@pytest.fixture
def environnement_vide(monkeypatch):
    for nom in (
        "SUPERVISOR_INTERVAL_SECONDS",
        "SUPERVISOR_DECISION_WINDOW_HOURS",
        "SUPERVISOR_ALERT_WINDOW_HOURS",
        "SUPERVISOR_GRACE_HOURS",
        "SUPERVISOR_LOCK_HOURS",
        "SUPERVISOR_MAX_MODEL_AGE_DAYS",
        "SUPERVISOR_MAE_TOLERANCE",
    ):
        monkeypatch.delenv(nom, raising=False)
    return monkeypatch


def test_les_defauts_sont_ceux_des_decisions_du_lot(environnement_vide):
    reglages = SupervisorSettings(_env_file=None)

    assert reglages.interval_seconds == 300
    assert reglages.decision_window == timedelta(days=7)
    assert reglages.alert_window == timedelta(hours=24)
    assert reglages.grace == timedelta(hours=24)
    assert reglages.lock == timedelta(hours=24)
    assert reglages.max_model_age == timedelta(days=7)
    assert reglages.mae_tolerance == 1.5


def test_chaque_reglage_se_lit_dans_l_environnement(environnement_vide):
    environnement_vide.setenv("SUPERVISOR_INTERVAL_SECONDS", "60")
    environnement_vide.setenv("SUPERVISOR_DECISION_WINDOW_HOURS", "48")
    environnement_vide.setenv("SUPERVISOR_ALERT_WINDOW_HOURS", "6")
    environnement_vide.setenv("SUPERVISOR_GRACE_HOURS", "2")
    environnement_vide.setenv("SUPERVISOR_LOCK_HOURS", "1")
    environnement_vide.setenv("SUPERVISOR_MAX_MODEL_AGE_DAYS", "3")
    environnement_vide.setenv("SUPERVISOR_MAE_TOLERANCE", "2.0")

    reglages = SupervisorSettings(_env_file=None)

    assert reglages.interval_seconds == 60
    assert reglages.decision_window == timedelta(hours=48)
    assert reglages.alert_window == timedelta(hours=6)
    assert reglages.grace == timedelta(hours=2)
    assert reglages.lock == timedelta(hours=1)
    assert reglages.max_model_age == timedelta(days=3)
    assert reglages.mae_tolerance == 2.0


@pytest.mark.parametrize(
    "nom",
    [
        "SUPERVISOR_INTERVAL_SECONDS",
        "SUPERVISOR_DECISION_WINDOW_HOURS",
        "SUPERVISOR_ALERT_WINDOW_HOURS",
        "SUPERVISOR_GRACE_HOURS",
        "SUPERVISOR_LOCK_HOURS",
        "SUPERVISOR_MAX_MODEL_AGE_DAYS",
        "SUPERVISOR_MAE_TOLERANCE",
    ],
)
@pytest.mark.parametrize("valeur", ["0", "-1"])
def test_une_valeur_nulle_ou_negative_est_refusee(environnement_vide, nom, valeur):
    environnement_vide.setenv(nom, valeur)

    with pytest.raises(ValidationError):
        SupervisorSettings(_env_file=None)


def test_les_variables_hors_prefixe_sont_ignorees(environnement_vide):
    environnement_vide.setenv("INTERVAL_SECONDS", "1")
    environnement_vide.setenv("COLLECTOR_INTERVAL_SECONDS", "1")

    assert SupervisorSettings(_env_file=None).interval_seconds == 300
