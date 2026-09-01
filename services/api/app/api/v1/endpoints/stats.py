from sqlalchemy import func, select

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.models.alert import Alert
from app.models.reading import Reading
from app.models.site import Site

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/summary")
def get_summary(_: CurrentUser, db: DbSession) -> dict[str, float | int]:
    values = func.coalesce(Reading.consumption_kwh_raw, Reading.consumption_kwh_imputed)
    return {
        "site_count": db.scalar(select(func.count(Site.id))) or 0,
        "reading_count": db.scalar(select(func.count(Reading.id))) or 0,
        "active_alert_count": db.scalar(select(func.count(Alert.id)).where(Alert.is_active.is_(True))) or 0,
        "average_consumption_kwh": round(db.scalar(select(func.avg(values))) or 0, 2),
    }
