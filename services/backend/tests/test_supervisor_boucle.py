"""Tests de la boucle du superviseur : un tour, une attente, recommencer.

La boucle ne decide rien, elle cadence l ordonnanceur et survit a ses echecs.
L attente est injectee : les tests ne dorment pas, ils comptent les appels et
arretent la boucle eux-memes en levant depuis l attente. La liste des sites
vient de la table `sites`, testee sur PostgreSQL avec des identifiants `SUP-*`.
"""

from datetime import UTC, datetime

import pytest
from app.db.models.site import Site
from app.db.session import SessionLocal
from app.supervisor.boucle import Boucle, sites_actifs
from sqlalchemy import delete

INTERVALLE = 300


class Arret(BaseException):  # noqa: N818 - pas une erreur, un signal de fin de test
    """Levee par l attente simulee pour sortir de la boucle sans fin."""


class FauxOrdonnanceur:
    def __init__(self, echecs_avant_succes: int = 0):
        self.tours = 0
        self.echecs_restants = echecs_avant_succes

    def tour(self) -> list[str]:
        self.tours += 1
        if self.echecs_restants > 0:
            self.echecs_restants -= 1
            raise RuntimeError("base injoignable")
        return ["demande"] * (self.tours % 2)


class Attente:
    def __init__(self, tours_avant_arret: int):
        self.durees: list[float] = []
        self.restants = tours_avant_arret

    def __call__(self, secondes: float) -> None:
        self.durees.append(secondes)
        self.restants -= 1
        if self.restants == 0:
            raise Arret


def test_la_boucle_enchaine_tour_attente_tour():
    ordonnanceur = FauxOrdonnanceur()
    attente = Attente(tours_avant_arret=3)

    with pytest.raises(Arret):
        Boucle(ordonnanceur, INTERVALLE, attendre=attente).run()

    assert ordonnanceur.tours == 3
    assert attente.durees == [INTERVALLE, INTERVALLE, INTERVALLE]


def test_un_tour_en_echec_n_arrete_pas_la_boucle(caplog):
    ordonnanceur = FauxOrdonnanceur(echecs_avant_succes=1)
    attente = Attente(tours_avant_arret=2)

    with caplog.at_level("ERROR", logger="app.supervisor.boucle"), pytest.raises(Arret):
        Boucle(ordonnanceur, INTERVALLE, attendre=attente).run()

    assert ordonnanceur.tours == 2
    assert "Tour de supervision en echec, reprise au prochain tour" in caplog.text


def test_le_demarrage_et_chaque_tour_sont_journalises(caplog):
    ordonnanceur = FauxOrdonnanceur()
    attente = Attente(tours_avant_arret=2)

    with caplog.at_level("INFO", logger="app.supervisor.boucle"), pytest.raises(Arret):
        Boucle(ordonnanceur, INTERVALLE, attendre=attente).run()

    assert "Superviseur demarre, un tour toutes les 300 s" in caplog.text
    assert "Tour termine : 1 demande(s) d entrainement" in caplog.text
    assert "Tour termine : 0 demande(s) d entrainement" in caplog.text


# --- Liste des sites, sur PostgreSQL -----------------------------------------


@pytest.fixture
def sites(database):
    instant = datetime(2026, 9, 1, tzinfo=UTC)

    def poser(site_id: str, status: str) -> None:
        with SessionLocal() as db:
            db.add(
                Site(
                    site_id=site_id,
                    site_type="test",
                    site_name=site_id,
                    location="nulle part",
                    capacity_kw=1.0,
                    status=status,
                    first_seen_at=instant,
                    last_seen_at=instant,
                )
            )
            db.commit()

    with SessionLocal() as db:
        db.execute(delete(Site).where(Site.site_id.like("SUP-%")))
        db.commit()
    yield poser
    with SessionLocal() as db:
        db.execute(delete(Site).where(Site.site_id.like("SUP-%")))
        db.commit()


def test_les_sites_actifs_sont_rendus_tries_sans_les_inactifs(sites):
    sites("SUP-B", "active")
    sites("SUP-A", "active")
    sites("SUP-C", "inactive")

    actifs = [s for s in sites_actifs(SessionLocal)() if s.startswith("SUP-")]

    assert actifs == ["SUP-A", "SUP-B"]


def test_la_liste_des_sites_est_relue_a_chaque_appel(sites):
    lister = sites_actifs(SessionLocal)
    sites("SUP-A", "active")

    assert "SUP-A" in lister()

    sites("SUP-B", "active")

    assert "SUP-B" in lister()
