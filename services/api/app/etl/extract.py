from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reading import Reading


def extract_readings_from_database(db: Session, since: datetime | None = None) -> list[Reading]:
    """Read locally persisted meter data; this project has no remote source."""
    statement = select(Reading).order_by(Reading.recorded_at)
    if since is not None:
        statement = statement.where(Reading.recorded_at > since)
    return list(db.scalars(statement))