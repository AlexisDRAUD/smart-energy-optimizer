import os
from collections.abc import Generator
from pathlib import Path

import pytest
from app.etl.extract import extract_from_json
from app.etl.transform import transform_readings

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="PostgreSQL ETL tests require an explicit TEST_DATABASE_URL.",
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "app" / "etl" / "fixtures" / "demo_readings.json"
)
ETL_SITE_IDS = (
    "SITE001",
    "SITE002",
    "SITE003",
    "SITE004",
    "SITE005",
    "ETL-ROLLBACK-OK",
    "ETL-ROLLBACK-BAD",
)


def _delete_etl_rows() -> None:
    from app.db.models.reading import Reading
    from app.db.session import SessionLocal
    from sqlalchemy import delete

    with SessionLocal() as db:
        db.execute(delete(Reading).where(Reading.site_id.in_(ETL_SITE_IDS)))
        db.commit()


@pytest.fixture
def clean_etl_rows(database: None) -> Generator[None, None, None]:
    _delete_etl_rows()
    yield
    _delete_etl_rows()


def test_json_pipeline_is_idempotent_in_postgresql(clean_etl_rows: None) -> None:
    from app.db.models.reading import Reading
    from app.db.session import SessionLocal
    from app.etl.load import load_readings
    from sqlalchemy import select

    raw_readings = extract_from_json(FIXTURE_PATH)
    transformed = transform_readings(raw_readings)

    assert len(raw_readings) == 5
    assert len(transformed.readings) == 4
    assert transformed.rejected_count == 1

    with SessionLocal() as db:
        first_load = load_readings(db, transformed.readings)
    with SessionLocal() as db:
        second_load = load_readings(db, transformed.readings)
    with SessionLocal() as db:
        stored_readings = list(
            db.scalars(
                select(Reading).where(Reading.site_id.in_(ETL_SITE_IDS)).order_by(Reading.site_id)
            )
        )

    assert first_load.inserted_count == 4
    assert first_load.skipped_count == 0
    assert second_load.inserted_count == 0
    assert second_load.skipped_count == 4
    assert [reading.site_id for reading in stored_readings] == [
        "SITE001",
        "SITE002",
        "SITE003",
        "SITE004",
    ]
    assert all(reading.is_imputed is False for reading in stored_readings)
    assert all(reading.imputation_method is None for reading in stored_readings)
    assert stored_readings[0].consumption_kwh_raw == 163.28
    assert stored_readings[0].consumption_kwh == 163.28
    assert stored_readings[3].consumption_kwh_raw is None
    assert stored_readings[3].consumption_kwh is None
    assert stored_readings[3].null_reasons == ["consumption_sensor_failure"]


def test_postgresql_error_rolls_back_entire_batch(clean_etl_rows: None) -> None:
    from app.db.models.reading import Reading
    from app.db.session import SessionLocal
    from app.etl.load import load_readings
    from sqlalchemy import func, select
    from sqlalchemy.exc import IntegrityError

    raw_reading = transform_readings(extract_from_json(FIXTURE_PATH)).readings[0]
    valid_reading = raw_reading.model_copy(update={"site_id": "ETL-ROLLBACK-OK"})
    invalid_reading = raw_reading.model_copy(
        update={"site_id": "ETL-ROLLBACK-BAD", "data_quality": "invalid"}
    )

    with SessionLocal() as db:
        with pytest.raises(IntegrityError):
            load_readings(
                db,
                [
                    valid_reading,
                    invalid_reading,
                ],
            )
        stored_count = db.scalar(
            select(func.count())
            .select_from(Reading)
            .where(Reading.site_id.in_(("ETL-ROLLBACK-OK", "ETL-ROLLBACK-BAD")))
        )

    assert stored_count == 0
