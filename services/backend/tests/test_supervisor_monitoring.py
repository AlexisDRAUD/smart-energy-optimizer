"""Tests du moniteur du superviseur ML : mesurer l erreur, sans rien decider.

Le moniteur lit la table `predictions`, deja notee par l API (actual_kwh et
absolute_error remplis quand la mesure reelle arrive), et rend par site :

- la MAE sur la fenetre de decision (7 jours par defaut) ;
- la MAE sur la fenetre d alerte (24 h par defaut), informative ;
- la version de modele en production, celle de la derniere prediction emise ;
- la premiere notation de cette version, pour la regle des 24 h apres promotion.

Seules les predictions de la version en production comptent : juste apres une
promotion, les erreurs de l ancien modele ne doivent pas juger le nouveau.

Aucune horloge reelle : l instant present est injecte. Les predictions de test
portent des identifiants de site `SUP-*` qui n existent pas dans le jeu de
demonstration, pour ne pas gener les autres tests.
"""

from datetime import UTC, datetime, timedelta

import pytest
from app.db.models.prediction import Prediction
from app.db.session import SessionLocal
from app.supervisor.monitoring import Moniteur
from sqlalchemy import delete

SITE = "SUP-TEST"
MAINTENANT = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
HORIZON_MINUTES = 120


@pytest.fixture
def moniteur(database):
    with SessionLocal() as db:
        db.execute(delete(Prediction).where(Prediction.site_id.like("SUP-%")))
        db.commit()
    return Moniteur(SessionLocal, horloge=lambda: MAINTENANT)


def il_y_a(**duree) -> datetime:
    return MAINTENANT - timedelta(**duree)


def _ajouter(target_at: datetime, predit: float, reel: float | None, version="v1", site=SITE):
    """Insere une prediction : notee si `reel` est renseigne, en attente sinon."""
    with SessionLocal() as db:
        db.add(
            Prediction(
                site_id=site,
                predicted_at=target_at - timedelta(minutes=HORIZON_MINUTES),
                target_at=target_at,
                horizon_minutes=HORIZON_MINUTES,
                model_name="modele-test",
                model_version=version,
                predicted_kwh=predit,
                actual_kwh=reel,
                scored_at=None if reel is None else target_at + timedelta(minutes=1),
            )
        )
        db.commit()


def test_sans_prediction_notee_il_n_y_a_pas_de_mesure(moniteur):
    rapport = moniteur.mesurer(SITE)

    assert rapport.site_id == SITE
    assert rapport.version_en_production is None
    assert rapport.mae_decision is None
    assert rapport.mae_alerte is None
    assert rapport.notees_decision == 0
    assert rapport.notees_alerte == 0
    assert rapport.premiere_notation is None


def test_la_mae_est_la_moyenne_des_erreurs_absolues_de_la_fenetre(moniteur):
    _ajouter(il_y_a(hours=1), predit=102.0, reel=100.0)  # erreur 2, dans les 24 h
    _ajouter(il_y_a(days=2), predit=96.0, reel=100.0)  # erreur 4
    _ajouter(il_y_a(days=6), predit=106.0, reel=100.0)  # erreur 6

    rapport = moniteur.mesurer(SITE)

    assert rapport.mae_decision == pytest.approx(4.0)
    assert rapport.notees_decision == 3
    assert rapport.mae_alerte == pytest.approx(2.0)
    assert rapport.notees_alerte == 1


def test_une_prediction_plus_vieille_que_la_fenetre_est_ignoree(moniteur):
    _ajouter(il_y_a(days=8), predit=200.0, reel=100.0)
    _ajouter(il_y_a(hours=1), predit=101.0, reel=100.0)

    rapport = moniteur.mesurer(SITE)

    assert rapport.mae_decision == pytest.approx(1.0)
    assert rapport.notees_decision == 1


def test_la_borne_basse_de_la_fenetre_est_incluse(moniteur):
    _ajouter(il_y_a(days=7), predit=103.0, reel=100.0)

    rapport = moniteur.mesurer(SITE)

    assert rapport.notees_decision == 1
    assert rapport.mae_decision == pytest.approx(3.0)


def test_une_prediction_pas_encore_notee_ne_compte_pas(moniteur):
    _ajouter(il_y_a(hours=1), predit=150.0, reel=None)
    _ajouter(il_y_a(hours=2), predit=101.0, reel=100.0)

    rapport = moniteur.mesurer(SITE)

    assert rapport.mae_decision == pytest.approx(1.0)
    assert rapport.notees_decision == 1


def test_seule_la_version_en_production_est_mesuree(moniteur):
    # Ancien modele, tres mauvais, encore dans la fenetre de decision.
    _ajouter(il_y_a(days=2), predit=150.0, reel=100.0, version="v1")
    # Nouveau modele : sa prediction plus recente en fait la version en production.
    _ajouter(il_y_a(hours=1), predit=101.0, reel=100.0, version="v2")

    rapport = moniteur.mesurer(SITE)

    assert rapport.version_en_production == "v2"
    assert rapport.mae_decision == pytest.approx(1.0)
    assert rapport.notees_decision == 1


def test_la_version_en_production_est_celle_de_la_derniere_prediction_emise(moniteur):
    # v2 a emis plus recemment, meme si sa prediction n est pas encore notee.
    _ajouter(il_y_a(hours=3), predit=101.0, reel=100.0, version="v1")
    _ajouter(il_y_a(hours=1), predit=99.0, reel=None, version="v2")

    rapport = moniteur.mesurer(SITE)

    assert rapport.version_en_production == "v2"
    assert rapport.mae_decision is None
    assert rapport.notees_decision == 0


def test_la_premiere_notation_de_la_version_en_production_est_connue(moniteur):
    _ajouter(il_y_a(days=10), predit=101.0, reel=100.0, version="v1")
    _ajouter(il_y_a(hours=30), predit=101.0, reel=100.0, version="v2")
    _ajouter(il_y_a(hours=1), predit=101.0, reel=100.0, version="v2")

    rapport = moniteur.mesurer(SITE)

    assert rapport.premiere_notation == il_y_a(hours=30)


def test_les_sites_ne_se_melangent_pas(moniteur):
    _ajouter(il_y_a(hours=1), predit=110.0, reel=100.0, site="SUP-TEST")
    _ajouter(il_y_a(hours=1), predit=101.0, reel=100.0, site="SUP-AUTRE")

    assert moniteur.mesurer("SUP-TEST").mae_decision == pytest.approx(10.0)
    assert moniteur.mesurer("SUP-AUTRE").mae_decision == pytest.approx(1.0)


def test_les_fenetres_sont_configurables(moniteur):
    court = Moniteur(
        SessionLocal,
        horloge=lambda: MAINTENANT,
        fenetre_decision=timedelta(hours=2),
        fenetre_alerte=timedelta(minutes=30),
    )
    _ajouter(il_y_a(minutes=10), predit=102.0, reel=100.0)  # erreur 2
    _ajouter(il_y_a(hours=1), predit=104.0, reel=100.0)  # erreur 4
    _ajouter(il_y_a(hours=3), predit=120.0, reel=100.0)  # hors fenetre

    rapport = court.mesurer(SITE)

    assert rapport.mae_decision == pytest.approx(3.0)
    assert rapport.mae_alerte == pytest.approx(2.0)
