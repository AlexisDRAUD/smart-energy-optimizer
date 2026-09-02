import json
import sqlite3
from pathlib import Path
from typing import Any

from etl.load import load_readings
from etl.transform import EnergyReading


def valid_payload() -> dict[str, Any]:
    return {
        "timestamp": "2026-09-02T12:23:23.083492",
        "site_id": "SITE001",
        "site_type": "office",
        "consumption_kw": 163.28,
        "consumption_kwh": 163.28,
        "voltage_v": 390.1,
        "current_a": 254.4,
        "power_factor": 0.947,
        "temperature_celsius": 13.5,
        "humidity_percent": 44.9,
        "null_reasons": [],
        "data_quality": "good",
    }


def test_loading_creates_database_and_persists_traceable_reading(tmp_path: Path) -> None:
    database_path = tmp_path / "nested" / "readings.sqlite3"
    reading = EnergyReading.from_source(valid_payload())

    result = load_readings(database_path, [reading])

    assert result.inserted_count == 1
    assert result.skipped_count == 0
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT site_id, timestamp, source_payload FROM energy_readings"
        ).fetchone()
    assert row is not None
    assert row[0] == "SITE001"
    assert row[1] == "2026-09-02T12:23:23.083492"
    assert json.loads(row[2]) == valid_payload()


def test_loading_same_reading_twice_does_not_create_duplicate(tmp_path: Path) -> None:
    database_path = tmp_path / "readings.sqlite3"
    reading = EnergyReading.from_source(valid_payload())

    first_result = load_readings(database_path, [reading])
    second_result = load_readings(database_path, [reading])

    assert first_result.inserted_count == 1
    assert second_result.inserted_count == 0
    assert second_result.skipped_count == 1
    with sqlite3.connect(database_path) as connection:
        row_count = connection.execute("SELECT COUNT(*) FROM energy_readings").fetchone()
    assert row_count == (1,)
