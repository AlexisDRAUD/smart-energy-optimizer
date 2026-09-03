"""SQLite loading adapter for validated energy readings."""

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from etl.transform import EnergyReading

CREATE_TABLE_SQL: Final = """
CREATE TABLE IF NOT EXISTS energy_readings (
    site_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    site_type TEXT NOT NULL,
    consumption_kw REAL,
    consumption_kwh REAL,
    voltage_v REAL,
    current_a REAL,
    power_factor REAL,
    temperature_celsius REAL,
    humidity_percent REAL,
    null_reasons TEXT NOT NULL,
    data_quality TEXT NOT NULL,
    source_payload TEXT NOT NULL,
    ingested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (site_id, timestamp)
)
"""

INSERT_READING_SQL: Final = """
INSERT OR IGNORE INTO energy_readings (
    site_id,
    timestamp,
    site_type,
    consumption_kw,
    consumption_kwh,
    voltage_v,
    current_a,
    power_factor,
    temperature_celsius,
    humidity_percent,
    null_reasons,
    data_quality,
    source_payload
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (site_id, timestamp) DO NOTHING
"""


@dataclass(frozen=True)
class LoadResult:
    inserted_count: int
    skipped_count: int


def initialize_database(connection: sqlite3.Connection) -> None:
    """Create the local table when it does not exist yet."""
    connection.execute(CREATE_TABLE_SQL)


def load_readings(database_path: Path, readings: list[EnergyReading]) -> LoadResult:
    """Insert readings idempotently using ``(site_id, timestamp)`` as the key."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    inserted_count = 0

    with sqlite3.connect(database_path) as connection:
        initialize_database(connection)
        for reading in readings:
            cursor = connection.execute(
                INSERT_READING_SQL,
                (
                    reading.site_id,
                    reading.timestamp.isoformat(),
                    reading.site_type,
                    reading.consumption_kw,
                    reading.consumption_kwh,
                    reading.voltage_v,
                    reading.current_a,
                    reading.power_factor,
                    reading.temperature_celsius,
                    reading.humidity_percent,
                    json.dumps(reading.null_reasons, ensure_ascii=False),
                    reading.data_quality,
                    json.dumps(reading.source_payload, ensure_ascii=False),
                ),
            )
            inserted_count += cursor.rowcount

    return LoadResult(
        inserted_count=inserted_count,
        skipped_count=len(readings) - inserted_count,
    )
