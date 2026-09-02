from sqlalchemy import func, select

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.models.alert import Alert
from app.models.reading import Reading

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/summary")
def get_summary(user: CurrentUser, db: DbSession) -> dict[str, float | int]:
    values = func.coalesce(Reading.consumption_kwh_raw, Reading.consumption_kwh_imputed)
    return {
        "site_count": 1,
        "reading_count": db.scalar(select(func.count(Reading.id)).where(Reading.site_id == user.site_id)) or 0,
        "active_alert_count": db.scalar(
            select(func.count(Alert.id)).where(Alert.site_id == user.site_id, Alert.is_active.is_(True))
        )
        or 0,
        "average_consumption_kwh": round(
            db.scalar(select(func.avg(values)).where(Reading.site_id == user.site_id)) or 0,
            2,
        ),
    }
