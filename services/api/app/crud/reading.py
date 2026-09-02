from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.reading import Reading


def get_readings(
    db: Session,
    site_id: str | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> list[Reading]:
    statement: Select[tuple[Reading]] = select(Reading)
    if site_id is not None:
        statement = statement.where(Reading.site_id == site_id)
    if start_at is not None:
        statement = statement.where(Reading.measured_at >= start_at)
    if end_at is not None:
        statement = statement.where(Reading.measured_at <= end_at)
    return list(db.scalars(statement.order_by(Reading.measured_at.desc())))