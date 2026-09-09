import os

import pytest
from app.collector.storage import PostgresStorage
from sqlalchemy import text


@pytest.fixture
def storage():
    if not os.environ.get("TEST_DATABASE_URL"):
        pytest.skip("PostgreSQL storage tests require an explicit TEST_DATABASE_URL.")
    url = os.environ["DATABASE_URL"]
    s = PostgresStorage(url)
    with s.engine.begin() as conn:
        conn.execute(text("DELETE FROM raw_readings"))
    yield s
    s.close()


def _read_raw(storage):
    with storage.engine.connect() as conn:
        result = conn.execute(text("SELECT source, payload FROM raw_readings"))
        return [dict(row._mapping) for row in result]


def test_store_raw_keeps_the_payload_as_received(storage):
    payload = '{"site_id": "SITE001", "consumption_kw": null}'

    storage.store_raw(source="api_current", payload=payload)

    rows = _read_raw(storage)
    assert len(rows) == 1
    assert rows[0]["source"] == "api_current"
    assert rows[0]["payload"] == {"site_id": "SITE001", "consumption_kw": None}


def test_two_inserts_make_two_rows(storage):
    storage.store_raw(source="api_current", payload='{"a": 1}')
    storage.store_raw(source="api_current", payload='{"a": 1}')

    assert len(_read_raw(storage)) == 2
