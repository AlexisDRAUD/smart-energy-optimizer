import os

import pytest
from collector.storage import PostgresStorage


@pytest.fixture
def storage():
    s = PostgresStorage(
        host="localhost",
        port="5432",
        user="seo",
        password=os.environ["POSTGRES_PASSWORD"],
        dbname="seo",
    )
    s.conn.execute("DELETE FROM raw_readings")
    s.conn.commit()
    yield s
    s.close()


def test_store_raw_conserve_le_payload_tel_quel(storage):
    payload = '{"site_id": "SITE001", "consumption_kw": null}'

    storage.store_raw(source="api_current", payload=payload)

    rows = storage.fetch_all_raw()
    assert len(rows) == 1
    assert rows[0]["source"] == "api_current"
    assert rows[0]["payload"] == {"site_id": "SITE001", "consumption_kw": None}


def test_deux_insertions_font_deux_lignes(storage):
    storage.store_raw(source="api_current", payload='{"a": 1}')
    storage.store_raw(source="api_current", payload='{"a": 1}')

    assert len(storage.fetch_all_raw()) == 2
