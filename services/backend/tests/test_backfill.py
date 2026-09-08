import json
import os

import pytest
from app.collector.backfill import Backfill, already_backfilled_sites, run_backfill
from app.collector.storage import PostgresStorage
from sqlalchemy import text

ONE_MINUTE = 60  # secondes


@pytest.fixture
def storage(database):
    s = PostgresStorage(os.environ["DATABASE_URL"])
    with s.engine.begin() as conn:
        conn.execute(text("DELETE FROM raw_readings"))
    yield s
    s.close()


def _read_backfill(storage):
    with storage.engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT source, payload FROM raw_readings WHERE source = 'api_backfill' ORDER BY id"
            )
        )
        return [dict(row._mapping) for row in result]


class FakeApi:
    """Rend des reponses preparees et memorise chaque appel recu."""

    def __init__(self, responses, failing_sites=()):
        self.responses = list(responses)
        self.calls = []
        self.failing_sites = set(failing_sites)

    def __call__(self, site_id, start_time, end_time, limit):
        self.calls.append(
            {"site_id": site_id, "start": start_time, "end": end_time, "limit": limit}
        )
        if site_id in self.failing_sites:
            raise RuntimeError(f"source indisponible pour {site_id}")
        return self.responses.pop(0) if self.responses else []


def test_measurements_are_stored_as_received(storage):
    measurements = [
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
    api = FakeApi([measurements])

    Backfill(storage, api, site_id="SITE001").run()

    rows = _read_backfill(storage)
    assert rows[0]["payload"]["consumption_kw"] is None
    assert rows[0]["payload"]["null_reasons"] == ["network_loss"]
    assert rows[1]["payload"]["consumption_kw"] == 70.9


def test_every_measurement_reaches_the_database(storage):
    window_1 = [{"timestamp": f"2024-09-01T00:{m:02d}:00", "site_id": "SITE001"} for m in range(3)]
    window_2 = [{"timestamp": f"2024-09-01T01:{m:02d}:00", "site_id": "SITE001"} for m in range(2)]
    api = FakeApi([window_1, window_2])

    Backfill(storage, api, site_id="SITE001").run()

    assert len(_read_backfill(storage)) == 5


def test_every_call_requests_a_one_minute_step(storage):
    api = FakeApi([])

    Backfill(storage, api, site_id="SITE001").run()

    assert len(api.calls) > 0
    for call in api.calls:
        duration = (call["end"] - call["start"]).total_seconds()
        assert duration / call["limit"] == ONE_MINUTE, (
            "Pas de generation = 1 mesure/minute. Une fenetre plus large "
            "degrade les donnees de la source (constat du 03/09)."
        )


def test_calls_target_only_the_requested_site(storage):
    api = FakeApi([])

    Backfill(storage, api, site_id="SITE003").run()

    assert all(call["site_id"] == "SITE003" for call in api.calls)


def test_running_again_creates_no_duplicates(storage):
    measurements = [
        {"timestamp": f"2024-09-01T00:{m:02d}:00", "site_id": "SITE001"} for m in range(3)
    ]

    Backfill(storage, FakeApi([measurements]), site_id="SITE001").run()
    Backfill(storage, FakeApi([measurements]), site_id="SITE001").run()

    assert len(_read_backfill(storage)) == 3


class ApiCutOffMidway:
    """Repond a la premiere fenetre puis coupe, comme une source qui tombe."""

    def __init__(self, first_window):
        self.first_window = first_window
        self.calls = 0

    def __call__(self, site_id, start_time, end_time, limit):
        self.calls += 1
        if self.calls == 1:
            return self.first_window
        raise RuntimeError("source coupee en cours de reprise")


def _sites_in_database(storage):
    with storage.engine.connect() as conn:
        return set(
            conn.execute(
                text("SELECT DISTINCT site_id FROM raw_readings WHERE source = 'api_backfill'")
            ).scalars()
        )


def test_a_site_cut_off_midway_leaves_no_row(storage):
    """Sinon il passerait pour repris, et son historique manquerait pour de bon."""
    measurements = [
        {"timestamp": f"2024-09-01T00:{m:02d}:00", "site_id": "SITE001"} for m in range(3)
    ]

    with pytest.raises(RuntimeError):
        Backfill(storage, ApiCutOffMidway(measurements), site_id="SITE001", days=2).run()

    assert _read_backfill(storage) == []


def test_a_failed_site_is_retried_on_the_next_start(storage):
    measurements_1 = [{"timestamp": "2024-09-01T00:00:00", "site_id": "SITE001"}]
    measurements_2 = [{"timestamp": "2024-09-01T00:00:00", "site_id": "SITE002"}]

    first_run = run_backfill(
        storage,
        FakeApi([measurements_1], failing_sites=["SITE002"]),
        ["SITE001", "SITE002"],
        days=1,
    )

    assert first_run.backfilled == ("SITE001",)
    assert first_run.failed == ("SITE002",)
    assert _sites_in_database(storage) == {"SITE001"}

    second_run = run_backfill(storage, FakeApi([measurements_2]), ["SITE001", "SITE002"], days=1)

    # SITE001 a deja le sien, seul SITE002 est redemande a la source.
    assert second_run.skipped == ("SITE001",)
    assert second_run.backfilled == ("SITE002",)
    assert second_run.failed == ()
    assert _sites_in_database(storage) == {"SITE001", "SITE002"}


def test_an_already_backfilled_site_is_not_requested_again(storage):
    measurements = [{"timestamp": "2024-09-01T00:00:00", "site_id": "SITE001"}]
    run_backfill(storage, FakeApi([measurements]), ["SITE001"], days=1)

    api = FakeApi([])
    result = run_backfill(storage, api, ["SITE001"], days=1)

    assert result.skipped == ("SITE001",)
    assert api.calls == []


def test_force_backfills_a_site_already_in_the_database(storage):
    measurements = [{"timestamp": "2024-09-01T00:00:00", "site_id": "SITE001"}]
    run_backfill(storage, FakeApi([measurements]), ["SITE001"], days=1)

    api = FakeApi([measurements])
    result = run_backfill(storage, api, ["SITE001"], days=1, force=True)

    assert result.backfilled == ("SITE001",)
    assert api.calls != []
    # La cle unique absorbe ce qui existait deja.
    assert len(_read_backfill(storage)) == 1


def test_collector_rows_do_not_mark_a_site_as_backfilled(storage):
    """api_current ne prouve que la minute courante, pas un historique."""
    storage.store_raw(
        "api_current", json.dumps({"timestamp": "2024-09-01T00:00:00", "site_id": "SITE001"})
    )

    assert already_backfilled_sites(storage) == set()
