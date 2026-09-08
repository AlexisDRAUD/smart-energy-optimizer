"""Tests du lanceur d entrainement du superviseur.

Le lanceur est ce que l ordonnanceur appelle quand il a decide de reentrainer
un site : un appelable qui recoit le site_id, rien d autre. LanceurJournal
est l implementation qui ne fait que journaliser, en place tant que le point
d entree du service ML n est pas appelable par une machine. Ce qui est
verifie : la ligne de journal, le contrat, et qu il se branche tel quel sur
l ordonnanceur.
"""

from datetime import UTC, datetime, timedelta

from app.supervisor.lanceur import LanceurJournal
from app.supervisor.monitoring import RapportSite
from app.supervisor.scheduler import Ordonnanceur, seuil_fixe

MAINTENANT = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)


def test_le_lanceur_journal_ecrit_une_ligne_info_par_site(caplog):
    lanceur = LanceurJournal()

    with caplog.at_level("INFO", logger="app.supervisor.lanceur"):
        lanceur("SITE001")
        lanceur("SITE007")

    lignes = [r.getMessage() for r in caplog.records if r.name == "app.supervisor.lanceur"]
    assert lignes == [
        "Lancement demande pour SITE001 (journal seulement, aucun entrainement declenche)",
        "Lancement demande pour SITE007 (journal seulement, aucun entrainement declenche)",
    ]
    assert all(r.levelname == "INFO" for r in caplog.records)


def test_le_lanceur_journal_ne_rend_rien():
    assert LanceurJournal()("SITE001") is None


def test_le_lanceur_journal_se_branche_sur_l_ordonnanceur(caplog):
    """Le contrat Lanceur est respecte : l ordonnanceur l appelle sans adaptation."""
    en_derive = RapportSite(
        site_id="SITE001",
        version_en_production="3",
        mae_decision=50.0,
        mae_alerte=50.0,
        notees_decision=100,
        notees_alerte=20,
        premiere_notation=MAINTENANT - timedelta(days=3),
    )
    ordonnanceur = Ordonnanceur(
        sites=lambda: ["SITE001"],
        mesurer=lambda site_id: en_derive,
        lanceur=LanceurJournal(),
        seuil=seuil_fixe(10.0),
        horloge=lambda: MAINTENANT,
    )

    with caplog.at_level("INFO", logger="app.supervisor.lanceur"):
        demandes = ordonnanceur.tour()

    assert [d.raison for d in demandes] == ["derive"]
    assert "Lancement demande pour SITE001" in caplog.text
