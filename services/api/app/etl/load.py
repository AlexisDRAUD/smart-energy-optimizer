from sqlalchemy.orm import Session

from app.models.reading import Reading


def load_readings(db: Session, readings: list[Reading]) -> int:
    """Persist transformed readings from a controlled local import."""
    db.add_all(readings)
    db.commit()
    return len(readings)