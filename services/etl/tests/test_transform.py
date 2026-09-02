import logging
from typing import Any

import pytest
from etl.transform import EnergyReading, transform_readings


def valid_payload() -> dict[str, Any]:
    return {
        "timestamp": "2026-09-02T12:23:23.083492",
        "site_id": "SITE001",
        "site_type": "office",
        "consumption_kw": "163.28",
        "consumption_kwh": 163.28,
        "voltage_v": 390.1,
        "current_a": 254.4,
        "power_factor": 0.947,
        "temperature_celsius": 13.5,
        "humidity_percent": 44.9,
        "null_reasons": [],
        "data_quality": "good",
    }


def test_valid_reading_is_normalized_without_losing_source_payload() -> None:
    payload = valid_payload()

    reading = EnergyReading.from_source(payload)

    assert reading.consumption_kw == 163.28
    assert reading.timestamp.isoformat() == "2026-09-02T12:23:23.083492"
    assert reading.site_id == "SITE001"
    assert reading.source_payload == payload
    assert reading.source_payload["consumption_kw"] == "163.28"


def test_missing_measure_stays_absent_from_normalized_payload() -> None:
    payload = valid_payload()
    del payload["temperature_celsius"]
    payload["null_reasons"] = ["temperature_sensor_failure"]
    payload["data_quality"] = "partial"

    reading = EnergyReading.from_source(payload)

    assert reading.temperature_celsius is None
    assert "temperature_celsius" not in reading.normalized_payload()
    assert "temperature_celsius" not in reading.source_payload


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("timestamp", "not-a-date"),
        ("site_id", "  "),
        ("site_type", 123),
        ("consumption_kw", -0.1),
        ("consumption_kwh", "not-a-number"),
        ("voltage_v", True),
        ("power_factor", 1.01),
        ("humidity_percent", 100.1),
        ("null_reasons", "sensor_failure"),
    ],
)
def test_invalid_values_are_rejected(field: str, invalid_value: Any) -> None:
    payload = valid_payload()
    payload[field] = invalid_value

    result = transform_readings([payload])

    assert result.readings == []
    assert result.rejected_count == 1


def test_invalid_row_is_logged_without_stopping_other_rows(
    caplog: pytest.LogCaptureFixture,
) -> None:
    invalid_payload = valid_payload()
    invalid_payload["power_factor"] = 2

    with caplog.at_level(logging.WARNING):
        result = transform_readings([invalid_payload, valid_payload()])

    assert len(result.readings) == 1
    assert result.rejected_count == 1
    assert "Ligne 1 rejetée" in caplog.text
