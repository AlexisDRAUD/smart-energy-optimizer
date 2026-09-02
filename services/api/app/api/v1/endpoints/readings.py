from datetime import datetime

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession, SiteUser
from app.crud.reading import create_reading, get_readings
from app.crud.site import get_site
from app.schemas.reading import ReadingCreate, ReadingRead
from app.services.alert_service import evaluate_reading_alert

router = APIRouter(prefix="/readings", tags=["readings"])


@router.get("", response_model=list[ReadingRead])
def list_readings(
    user: CurrentUser,
    db: DbSession,
    site_id: int | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> list[ReadingRead]:
    if site_id is not None and site_id != user.site_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to this site is forbidden")
    return get_readings(db, user.site_id, start_at, end_at)


@router.post(
    "/sites/{site_id}",
    response_model=ReadingRead,
    status_code=status.HTTP_201_CREATED,
)
def create_site_reading(
    site_id: int,
    reading_in: ReadingCreate,
    db: DbSession,
    _: SiteUser,
) -> ReadingRead:
    if get_site(db, site_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    reading = create_reading(db, site_id, reading_in)
    evaluate_reading_alert(db, reading)
    return reading
