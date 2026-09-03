"""PostgreSQL loading adapter for validated energy readings."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models.reading import Reading
from app.etl.transform import EnergyReading


@dataclass(frozen=True)
class LoadResult:
    inserted_count: int
    skipped_count: int


def load_readings(db: Session, readings: Sequence[EnergyReading]) -> LoadResult:
    """Insert readings atomically and ignore only duplicate measurement keys."""
    if not readings:
        return LoadResult(inserted_count=0, skipped_count=0)

    ingested_at = datetime.now(UTC)
    values = [
        {
            "site_id": reading.site_id,
            "measured_at": reading.timestamp,
            "consumption_kwh_raw": reading.consumption_kwh,
            "consumption_kwh": reading.consumption_kwh,
            "is_imputed": False,
            "imputation_method": None,
            "temperature_celsius": reading.temperature_celsius,
            "humidity_percent": reading.humidity_percent,
            "data_quality": reading.data_quality,
            "null_reasons": reading.null_reasons,
            "ingested_at": ingested_at,
        }
        for reading in readings
    ]
    statement = (
        insert(Reading)
        .values(values)
        .on_conflict_do_nothing(constraint="uq_readings_site_measured")
        .returning(Reading.site_id)
    )

    try:
        inserted_count = len(db.execute(statement).scalars().all())
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    return LoadResult(
        inserted_count=inserted_count,
        skipped_count=len(readings) - inserted_count,
    )
