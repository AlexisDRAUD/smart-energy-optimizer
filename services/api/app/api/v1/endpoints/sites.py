from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession, RoleChecker
from app.crud.site import create_site, get_site, get_sites
from app.models.reading import Reading
from app.schemas.reading import ReadingRead
from app.schemas.site import SiteCreate, SiteRead

router = APIRouter(prefix="/sites", tags=["sites"])
require_operator = RoleChecker("admin", "operator")


@router.get("", response_model=list[SiteRead])
def list_sites(_: CurrentUser, db: DbSession) -> list[SiteRead]:
    return get_sites(db)


@router.post(
    "",
    response_model=SiteRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_operator)],
)
def create_new_site(db: DbSession, site_in: SiteCreate) -> SiteRead:
    try:
        return create_site(db, site_in)
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Site code already exists") from error


@router.get("/{site_id}", response_model=SiteRead)
def get_site_detail(site_id: int, _: CurrentUser, db: DbSession) -> SiteRead:
    site = get_site(db, site_id)
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    return site


@router.get("/{site_id}/current", response_model=ReadingRead)
def get_current_reading(site_id: int, _: CurrentUser, db: DbSession) -> ReadingRead:
    if get_site(db, site_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    reading = db.scalar(
        select(Reading).where(Reading.site_id == site_id).order_by(Reading.recorded_at.desc()).limit(1)
    )
    if reading is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No reading available for this site")
    return reading
