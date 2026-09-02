from collector.storage import SqliteStorage


def test_store_raw_conserve_le_payload_tel_quel(tmp_path):
    storage = SqliteStorage(tmp_path / "test.db")
    payload = '{"site_id": "SITE001", "consumption_kw": null}'

    storage.store_raw(source="api_current", payload=payload)

    rows = storage.fetch_all_raw()
    assert len(rows) == 1
    assert rows[0]["source"] == "api_current"
    assert rows[0]["payload"] == payload


def test_deux_insertions_font_deux_lignes(tmp_path):
    storage = SqliteStorage(tmp_path / "test.db")
    storage.store_raw(source="api_current", payload='{"a": 1}')
    storage.store_raw(source="api_current", payload='{"a": 1}')

    assert len(storage.fetch_all_raw()) == 2
