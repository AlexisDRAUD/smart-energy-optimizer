from datetime import datetime

from sqlalchemy.orm import Session

from app.etl.extract import extract_readings_from_database
from app.etl.transform import impute_missing_consumption


def process_stored_readings(db: Session, since: datetime | None = None) -> int:
    """Apply the ETL quality treatment to readings already stored in the database."""
    readings = extract_readings_from_database(db, since)
    impute_missing_consumption(readings)
    db.commit()
    return len(readings)