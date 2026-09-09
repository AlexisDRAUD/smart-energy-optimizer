"""Tests de l ordonnanceur du superviseur ML : decider et lancer, sans mesurer.

Aucune base ici. La mesure est un rapport prepare a l avance, l horloge est
fixee, et le lanceur note les sites qu on lui demande. Ce qui est verifie, c est
la decision : quand on demande un entrainement, et surtout quand on ne le
demande pas (verrou, moins de 24 h de donnees, pas de seuil).
"""

from datetime import UTC, datetime, timedelta

import pytest
from app.supervisor.monitoring import RapportSite
from app.supervisor.scheduler import DemandeEntrainement, Ordonnanceur, seuil_fixe

SITE = "SITE001"
MAINTENANT = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
SEUIL = 10.0


def il_y_a(**duree) -> datetime:
    return MAINTENANT - timedelta(**duree)


EN_PLACE_DEPUIS_3_JOURS = il_y_a(days=3)


def rapport(
    site_id: str = SITE,
    version: str | None = "v1",
    mae_decision: float | None = 5.0,
    mae_alerte: float | None = 5.0,
    notees_decision: int = 100,
    notees_alerte: int = 20,
    premiere_notation: datetime | None = EN_PLACE_DEPUIS_3_JOURS,
) -> RapportSite:
    """Un site sain par defaut : modele en place depuis 3 jours, erreur sous le seuil."""
    return RapportSite(
        site_id=site_id,
        version_en_production=version,
        mae_decision=mae_decision,
        mae_alerte=mae_alerte,
        notees_decision=notees_decision,
        notees_alerte=notees_alerte,
        premiere_notation=premiere_notation,
    )


class Horloge:
    def __init__(self, instant: datetime = MAINTENANT):
        self.instant = instant

    def __call__(self) -> datetime:
        return self.instant

    def avancer(self, **duree) -> None:
        self.instant += timedelta(**duree)


class Banc:
    """Un ordonnanceur cable sur des rapports prepares et un lanceur qui note les sites."""

    def __init__(self, seuil: float | None = SEUIL, **reglages):
        self.rapports: dict[str, RapportSite] = {}
        self.lances: list[str] = []
        self.horloge = Horloge()
        self.ordonnanceur = Ordonnanceur(
            sites=lambda: list(self.rapports),
            mesurer=lambda site_id: self.rapports[site_id],
            lanceur=self.lances.append,
            seuil=seuil_fixe(seuil),
            horloge=self.horloge,
            **reglages,
        )

    def poser(self, *rapports: RapportSite) -> None:
        for r in rapports:
            self.rapports[r.site_id] = r

    def tour(self) -> list[DemandeEntrainement]:
        return self.ordonnanceur.tour()


@pytest.fixture
def banc() -> Banc:
    return Banc()


# --- Rien a faire ---------------------------------------------------------


def test_un_site_sain_ne_declenche_rien(banc):
    banc.poser(rapport())

    assert banc.tour() == []
    assert banc.lances == []


def test_sans_version_en_production_il_n_y_a_rien_a_surveiller(banc):
    banc.poser(rapport(version=None, mae_decision=None, premiere_notation=None))

    assert banc.tour() == []


def test_sans_seuil_mlflow_la_supervision_du_site_est_inactive(caplog):
    """Version sans modele MLflow (regle simple) : ni derive, ni filet, quel que
    soit l age du modele. Le premier entrainement d un site est une decision
    manuelle. Le site est signale et on passe au suivant."""
    banc = Banc(seuil=None)
    banc.poser(
        rapport(site_id="A", mae_decision=999.0),
        rapport(site_id="B", mae_decision=999.0, premiere_notation=il_y_a(days=8)),
        rapport(site_id="C", mae_decision=999.0, premiere_notation=il_y_a(days=30)),
    )

    with caplog.at_level("WARNING", logger="app.supervisor.scheduler"):
        assert banc.tour() == []

    assert banc.lances == []
    for site_id in ("A", "B", "C"):
        assert f"Site {site_id} : sans modele MLflow, supervision inactive" in caplog.text


def test_un_site_sans_seuil_n_empeche_pas_les_autres_d_etre_juges():
    sans_seuil = "B"
    banc = Banc()
    banc.ordonnanceur.seuil = lambda site_id, version: None if site_id == sans_seuil else SEUIL
    banc.poser(
        rapport(site_id="A", mae_decision=50.0),
        rapport(site_id=sans_seuil, mae_decision=50.0, premiere_notation=il_y_a(days=8)),
        rapport(site_id="C", mae_decision=50.0),
    )

    assert [d.site_id for d in banc.tour()] == ["A", "C"]
    assert banc.lances == ["A", "C"]


# --- Derive ---------------------------------------------------------------


def test_une_mae_au_dessus_du_seuil_demande_un_entrainement(banc):
    banc.poser(rapport(mae_decision=12.0))

    demandes = banc.tour()

    assert len(demandes) == 1
    demande = demandes[0]
    assert demande.site_id == SITE
    assert demande.raison == "derive"
    assert demande.version_en_production == "v1"
    assert demande.mae_decision == 12.0
    assert demande.seuil == SEUIL
    assert demande.demandee_at == MAINTENANT
    assert banc.lances == [SITE]


def test_le_lanceur_recoit_le_site_id_et_rien_d_autre(banc):
    appels: list[tuple[tuple, dict]] = []
    banc.ordonnanceur.lanceur = lambda *args, **kwargs: appels.append((args, kwargs))
    banc.poser(rapport(mae_decision=50.0))

    banc.tour()

    assert appels == [((SITE,), {})]


def test_une_mae_egale_au_seuil_ne_declenche_pas(banc):
    banc.poser(rapport(mae_decision=SEUIL))

    assert banc.tour() == []


def test_un_modele_n_est_pas_juge_avant_24_h_de_donnees(banc):
    """L unite est le temps depuis la premiere notation, pas un nombre de points."""
    banc.poser(rapport(mae_decision=50.0, premiere_notation=il_y_a(hours=23, minutes=59)))

    assert banc.tour() == []

    banc.poser(rapport(mae_decision=50.0, premiere_notation=il_y_a(hours=24)))

    assert [d.raison for d in banc.tour()] == ["derive"]


def test_le_nombre_de_predictions_notees_ne_compte_pas(banc):
    """Deux points seulement, mais notes depuis plus de 24 h : le verdict tombe."""
    banc.poser(rapport(mae_decision=50.0, notees_decision=2, notees_alerte=0))

    assert [d.raison for d in banc.tour()] == ["derive"]


def test_un_modele_jamais_note_n_est_pas_juge(banc):
    banc.poser(rapport(mae_decision=None, notees_decision=0, premiere_notation=None))

    assert banc.tour() == []


def test_la_fenetre_d_alerte_avertit_sans_declencher(banc, caplog):
    banc.poser(rapport(mae_decision=5.0, mae_alerte=30.0))

    with caplog.at_level("WARNING", logger="app.supervisor.scheduler"):
        demandes = banc.tour()

    assert demandes == []
    assert "au-dessus du seuil" in caplog.text


# --- Verrou ---------------------------------------------------------------


def test_le_verrou_empeche_de_redemander_avant_24_h(banc):
    banc.poser(rapport(mae_decision=50.0))

    assert len(banc.tour()) == 1
    assert banc.tour() == []

    banc.horloge.avancer(hours=23, minutes=59)
    assert banc.tour() == []

    banc.horloge.avancer(minutes=1)
    assert len(banc.tour()) == 1
    assert banc.lances == [SITE, SITE]


def test_le_verrou_est_par_site(banc):
    banc.poser(rapport(site_id="A", mae_decision=50.0), rapport(site_id="B", mae_decision=5.0))

    assert [d.site_id for d in banc.tour()] == ["A"]

    banc.poser(rapport(site_id="B", mae_decision=50.0))

    assert [d.site_id for d in banc.tour()] == ["B"]


# --- Filet ----------------------------------------------------------------


def test_un_modele_de_plus_de_7_jours_est_reentraine_meme_sans_derive(banc):
    banc.poser(rapport(mae_decision=1.0, premiere_notation=il_y_a(days=6, hours=23)))

    assert banc.tour() == []

    banc.poser(rapport(mae_decision=1.0, premiere_notation=il_y_a(days=7)))

    demandes = banc.tour()
    assert [d.raison for d in demandes] == ["filet"]
    assert demandes[0].mae_decision == 1.0


def test_le_filet_attend_7_jours_apres_un_lancement_non_promu(banc):
    """Le modele a ete reentraine mais pas promu : le filet ne le relance pas chaque jour."""
    banc.poser(rapport(mae_decision=1.0, premiere_notation=il_y_a(days=8)))
    assert [d.raison for d in banc.tour()] == ["filet"]

    banc.horloge.avancer(days=6)
    assert banc.tour() == []

    banc.horloge.avancer(days=1)
    assert [d.raison for d in banc.tour()] == ["filet"]


def test_apres_un_filet_une_derive_est_redemandee_des_la_fin_du_verrou(banc):
    """Le filet pose le meme verrou de 24 h ; ensuite la derive reprend la main."""
    banc.poser(rapport(mae_decision=50.0, premiere_notation=il_y_a(days=8)))
    assert [d.raison for d in banc.tour()] == ["filet"]

    banc.horloge.avancer(hours=12)
    assert banc.tour() == []

    banc.horloge.avancer(hours=12)
    assert [d.raison for d in banc.tour()] == ["derive"]


# --- Journal ----------------------------------------------------------------


def test_chaque_site_juge_laisse_une_ligne_info(banc, caplog):
    """Une ligne par site et par tour : MAE 7 j, MAE 24 h, seuil, verdict, dernier lancement."""
    banc.poser(
        rapport(site_id="SAIN", mae_decision=5.0, mae_alerte=4.5),
        rapport(site_id="DERIVE", mae_decision=12.0, mae_alerte=13.0),
        rapport(site_id="FRAIS", mae_decision=50.0, premiere_notation=il_y_a(hours=2)),
        rapport(site_id="VIDE", mae_decision=None, mae_alerte=None, premiere_notation=None),
    )

    with caplog.at_level("INFO", logger="app.supervisor.scheduler"):
        banc.tour()

    assert (
        "Site SAIN : MAE 7 j 5.000, MAE 24 h 4.500, seuil 10.000, "
        "verdict aucun, dernier lancement jamais"
    ) in caplog.text
    assert (
        "Site DERIVE : MAE 7 j 12.000, MAE 24 h 13.000, seuil 10.000, "
        "verdict derive, dernier lancement jamais"
    ) in caplog.text
    assert (
        "Site FRAIS : MAE 7 j 50.000, MAE 24 h 5.000, seuil 10.000, verdict grace," in caplog.text
    )
    assert "Site VIDE : MAE 7 j -, MAE 24 h -, seuil 10.000, verdict grace," in caplog.text


def test_la_ligne_info_montre_le_verrou_et_le_dernier_lancement(banc, caplog):
    banc.poser(rapport(mae_decision=12.0))
    banc.tour()
    banc.horloge.avancer(hours=6)

    with caplog.at_level("INFO", logger="app.supervisor.scheduler"):
        banc.tour()

    assert (
        "Site SITE001 : MAE 7 j 12.000, MAE 24 h 5.000, seuil 10.000, "
        "verdict verrou, dernier lancement 2026-09-08T12:00:00+00:00"
    ) in caplog.text


def test_un_site_sans_seuil_n_a_que_son_avertissement(caplog):
    banc = Banc(seuil=None)
    banc.poser(rapport())

    with caplog.at_level("INFO", logger="app.supervisor.scheduler"):
        banc.tour()

    assert "supervision inactive" in caplog.text
    assert "verdict" not in caplog.text


# --- Robustesse et reglages -------------------------------------------------


def test_un_site_en_erreur_n_empeche_pas_les_autres(banc, caplog):
    banc.poser(rapport(site_id="A", mae_decision=50.0), rapport(site_id="B", mae_decision=50.0))

    def mesurer(site_id: str) -> RapportSite:
        if site_id == "A":
            raise RuntimeError("base injoignable")
        return banc.rapports[site_id]

    banc.ordonnanceur.mesurer = mesurer

    with caplog.at_level("ERROR", logger="app.supervisor.scheduler"):
        demandes = banc.tour()

    assert [d.site_id for d in demandes] == ["B"]
    assert "Site A : examen interrompu" in caplog.text


def test_un_lanceur_qui_echoue_ne_pose_pas_le_verrou(banc):
    banc.poser(rapport(mae_decision=50.0))

    def lanceur_en_panne(site_id: str) -> None:
        raise RuntimeError("panne")

    banc.ordonnanceur.lanceur = lanceur_en_panne

    assert banc.tour() == []

    banc.ordonnanceur.lanceur = banc.lances.append
    assert len(banc.tour()) == 1


def test_les_reglages_sont_configurables():
    banc = Banc(
        delai_entre_lancements=timedelta(hours=1),
        delai_de_grace=timedelta(hours=1),
        age_maximal=timedelta(days=1),
    )
    banc.poser(rapport(mae_decision=50.0, premiere_notation=il_y_a(hours=1)))

    assert [d.raison for d in banc.tour()] == ["derive"]

    banc.horloge.avancer(hours=1)
    assert [d.raison for d in banc.tour()] == ["derive"]

    banc.poser(rapport(mae_decision=1.0, premiere_notation=il_y_a(days=1)))
    banc.horloge.avancer(days=1)
    assert [d.raison for d in banc.tour()] == ["filet"]


def test_le_seuil_fixe_ignore_le_site_et_la_version():
    source = seuil_fixe(3.5)

    assert source("A", "v1") == 3.5
    assert source("B", "v9") == 3.5
    assert seuil_fixe(None)("A", "v1") is None
