import os

import pytest
from app.collector.storage import PostgresStorage
from sqlalchemy import text


@pytest.fixture
def storage():
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://seo:1234@127.0.0.1:5432/seo",
    )
    s = PostgresStorage(url)
    with s.engine.begin() as conn:
        conn.execute(text("DELETE FROM raw_readings"))
    yield s
    s.close()


def _lire_raw(storage):
    with storage.engine.connect() as conn:
        result = conn.execute(text("SELECT source, payload FROM raw_readings"))
        return [dict(row._mapping) for row in result]


def test_store_raw_conserve_le_payload_tel_quel(storage):
    payload = '{"site_id": "SITE001", "consumption_kw": null}'

    storage.store_raw(source="api_current", payload=payload)

    rows = _lire_raw(storage)
    assert len(rows) == 1
    assert rows[0]["source"] == "api_current"
    assert rows[0]["payload"] == {"site_id": "SITE001", "consumption_kw": None}


def test_deux_insertions_font_deux_lignes(storage):
    storage.store_raw(source="api_current", payload='{"a": 1}')
    storage.store_raw(source="api_current", payload='{"a": 1}')

    assert len(_lire_raw(storage)) == 2
