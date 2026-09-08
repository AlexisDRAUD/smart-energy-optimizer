import json
import os

import pytest
from app.collector.backfill import Backfill, run_backfill, sites_deja_repris
from app.collector.storage import PostgresStorage
from sqlalchemy import text

UNE_MINUTE = 60  # secondes


@pytest.fixture
def storage(database):
    s = PostgresStorage(os.environ["DATABASE_URL"])
    with s.engine.begin() as conn:
        conn.execute(text("DELETE FROM raw_readings"))
    yield s
    s.close()


def _lire_backfill(storage):
    with storage.engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT source, payload FROM raw_readings WHERE source = 'api_backfill' ORDER BY id"
            )
        )
        return [dict(row._mapping) for row in result]


class FausseApi:
    """Rend des reponses preparees et memorise chaque appel recu."""

    def __init__(self, reponses, sites_en_echec=()):
        self.reponses = list(reponses)
        self.appels = []
        self.sites_en_echec = set(sites_en_echec)

    def __call__(self, site_id, start_time, end_time, limit):
        self.appels.append(
            {"site_id": site_id, "start": start_time, "end": end_time, "limit": limit}
        )
        if site_id in self.sites_en_echec:
            raise RuntimeError(f"source indisponible pour {site_id}")
        return self.reponses.pop(0) if self.reponses else []


def test_stocke_les_mesures_telles_quelles(storage):
    mesures = [
        {
            "timestamp": "2024-09-01T00:00:00",
            "site_id": "SITE001",
            "consumption_kw": None,
            "null_reasons": ["network_loss"],
            "data_quality": "critical",
        },
        {
            "timestamp": "2024-09-01T00:01:00",
            "site_id": "SITE001",
            "consumption_kw": 70.9,
            "null_reasons": [],
            "data_quality": "good",
        },
    ]
    api = FausseApi([mesures])

    Backfill(storage, api, site_id="SITE001").run()

    rows = _lire_backfill(storage)
    assert rows[0]["payload"]["consumption_kw"] is None
    assert rows[0]["payload"]["null_reasons"] == ["network_loss"]
    assert rows[1]["payload"]["consumption_kw"] == 70.9


def test_toutes_les_mesures_arrivent_en_base(storage):
    fenetre_1 = [{"timestamp": f"2024-09-01T00:{m:02d}:00", "site_id": "SITE001"} for m in range(3)]
    fenetre_2 = [{"timestamp": f"2024-09-01T01:{m:02d}:00", "site_id": "SITE001"} for m in range(2)]
    api = FausseApi([fenetre_1, fenetre_2])

    Backfill(storage, api, site_id="SITE001").run()

    assert len(_lire_backfill(storage)) == 5


def test_chaque_appel_demande_un_pas_d_une_minute(storage):
    api = FausseApi([])

    Backfill(storage, api, site_id="SITE001").run()

    assert len(api.appels) > 0
    for appel in api.appels:
        duree = (appel["end"] - appel["start"]).total_seconds()
        assert duree / appel["limit"] == UNE_MINUTE, (
            "Pas de generation = 1 mesure/minute. Une fenetre plus large "
            "degrade les donnees de la source (constat du 03/09)."
        )


def test_les_appels_ne_visent_que_le_site_demande(storage):
    api = FausseApi([])

    Backfill(storage, api, site_id="SITE003").run()

    assert all(a["site_id"] == "SITE003" for a in api.appels)


def test_relancer_ne_cree_pas_de_doublons(storage):
    mesures = [{"timestamp": f"2024-09-01T00:{m:02d}:00", "site_id": "SITE001"} for m in range(3)]

    Backfill(storage, FausseApi([mesures]), site_id="SITE001").run()
    Backfill(storage, FausseApi([mesures]), site_id="SITE001").run()

    assert len(_lire_backfill(storage)) == 3


class ApiQuiCoupe:
    """Repond a la premiere fenetre puis coupe, comme une source qui tombe."""

    def __init__(self, premiere_fenetre):
        self.premiere_fenetre = premiere_fenetre
        self.appels = 0

    def __call__(self, site_id, start_time, end_time, limit):
        self.appels += 1
        if self.appels == 1:
            return self.premiere_fenetre
        raise RuntimeError("source coupee en cours de reprise")


def _sites_en_base(storage):
    with storage.engine.connect() as conn:
        return set(
            conn.execute(
                text("SELECT DISTINCT site_id FROM raw_readings WHERE source = 'api_backfill'")
            ).scalars()
        )


def test_un_site_coupe_en_cours_de_route_ne_laisse_aucune_ligne(storage):
    """Sinon il passerait pour repris, et son historique manquerait pour de bon."""
    mesures = [{"timestamp": f"2024-09-01T00:{m:02d}:00", "site_id": "SITE001"} for m in range(3)]

    with pytest.raises(RuntimeError):
        Backfill(storage, ApiQuiCoupe(mesures), site_id="SITE001", days=2).run()

    assert _lire_backfill(storage) == []


def test_un_site_en_echec_est_repris_au_demarrage_suivant(storage):
    mesures_1 = [{"timestamp": "2024-09-01T00:00:00", "site_id": "SITE001"}]
    mesures_2 = [{"timestamp": "2024-09-01T00:00:00", "site_id": "SITE002"}]

    premier = run_backfill(
        storage,
        FausseApi([mesures_1], sites_en_echec=["SITE002"]),
        ["SITE001", "SITE002"],
        days=1,
    )

    assert premier.backfilled == ("SITE001",)
    assert premier.failed == ("SITE002",)
    assert _sites_en_base(storage) == {"SITE001"}

    second = run_backfill(storage, FausseApi([mesures_2]), ["SITE001", "SITE002"], days=1)

    # SITE001 a deja le sien, seul SITE002 est redemande a la source.
    assert second.skipped == ("SITE001",)
    assert second.backfilled == ("SITE002",)
    assert second.failed == ()
    assert _sites_en_base(storage) == {"SITE001", "SITE002"}


def test_un_site_deja_repris_n_est_pas_redemande_a_la_source(storage):
    mesures = [{"timestamp": "2024-09-01T00:00:00", "site_id": "SITE001"}]
    run_backfill(storage, FausseApi([mesures]), ["SITE001"], days=1)

    api = FausseApi([])
    resultat = run_backfill(storage, api, ["SITE001"], days=1)

    assert resultat.skipped == ("SITE001",)
    assert api.appels == []


def test_force_reprend_un_site_deja_en_base(storage):
    mesures = [{"timestamp": "2024-09-01T00:00:00", "site_id": "SITE001"}]
    run_backfill(storage, FausseApi([mesures]), ["SITE001"], days=1)

    api = FausseApi([mesures])
    resultat = run_backfill(storage, api, ["SITE001"], days=1, force=True)

    assert resultat.backfilled == ("SITE001",)
    assert api.appels != []
    # La cle unique absorbe ce qui existait deja.
    assert len(_lire_backfill(storage)) == 1


def test_les_lignes_du_collecteur_ne_font_pas_passer_un_site_pour_repris(storage):
    """api_current ne prouve que la minute courante, pas un historique."""
    storage.store_raw(
        "api_current", json.dumps({"timestamp": "2024-09-01T00:00:00", "site_id": "SITE001"})
    )

    assert sites_deja_repris(storage) == set()
