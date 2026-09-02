from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, SiteUser
from app.crud.site import get_site
from app.models.reading import Reading
from app.schemas.reading import ReadingRead
from app.schemas.site import SiteRead

router = APIRouter(prefix="/sites", tags=["sites"])


@router.get("", response_model=list[SiteRead])
def list_sites(user: CurrentUser, db: DbSession) -> list[SiteRead]:
    site = get_site(db, user.site_id)
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated site not found")
    return [site]


@router.get("/{site_id}", response_model=SiteRead)
def get_site_detail(site_id: int, _: SiteUser, db: DbSession) -> SiteRead:
    site = get_site(db, site_id)
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    return site


@router.get("/{site_id}/current", response_model=ReadingRead)
def get_current_reading(site_id: int, _: SiteUser, db: DbSession) -> ReadingRead:
    if get_site(db, site_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    reading = db.scalar(
        select(Reading)
        .where(Reading.site_id == site_id, Reading.source != "prediction")
        .order_by(Reading.recorded_at.desc())
        .limit(1)
    )
    if reading is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No reading available for this site")
    return reading
