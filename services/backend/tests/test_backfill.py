import os

import pytest
from app.collector.backfill import Backfill
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

    def __init__(self, reponses):
        self.reponses = list(reponses)
        self.appels = []

    def __call__(self, site_id, start_time, end_time, limit):
        self.appels.append(
            {"site_id": site_id, "start": start_time, "end": end_time, "limit": limit}
        )
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
