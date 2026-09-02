from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.reading import Reading
from app.schemas.reading import ReadingCreate


def get_readings(
    db: Session,
    site_id: int | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> list[Reading]:
    statement: Select[tuple[Reading]] = select(Reading)
    if site_id is not None:
        statement = statement.where(Reading.site_id == site_id)
    if start_at is not None:
        statement = statement.where(Reading.recorded_at >= start_at)
    if end_at is not None:
        statement = statement.where(Reading.recorded_at <= end_at)
    return list(db.scalars(statement.order_by(Reading.recorded_at.desc())))


def create_reading(db: Session, site_id: int, reading_in: ReadingCreate, source: str = "api") -> Reading:
    reading = Reading(site_id=site_id, source=source, **reading_in.model_dump())
    db.add(reading)
    db.commit()
    db.refresh(reading)
    return reading