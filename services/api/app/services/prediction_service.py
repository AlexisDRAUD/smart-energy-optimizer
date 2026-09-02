from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reading import Reading


def get_stored_next_prediction(db: Session, site_id: int) -> Reading:
    prediction = db.scalar(
        select(Reading)
        .where(Reading.site_id == site_id, Reading.source == "prediction")
        .order_by(Reading.recorded_at)
        .limit(1)
    )
    if prediction is None:
        raise ValueError("No prediction is available for this site")
    return prediction
