from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.api.v1.serializers import site_response
from app.core.contract import as_utc, utc_iso, utc_now
from app.db.models.reading import Reading
from app.db.models.site import Site
from app.schemas.contract import LatestReadingResponse, SiteResponse, SitesResponse

router = APIRouter(prefix="/sites", tags=["sites"])


def _site_or_404(db: DbSession, site_id: str) -> Site:
    site = db.get(Site, site_id)
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    return site


@router.get("", response_model=SitesResponse)
def list_sites(
    _: CurrentUser,
    db: DbSession,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    total = db.scalar(select(func.count(Site.site_id))) or 0
    sites = list(db.scalars(select(Site).order_by(Site.site_name).offset(offset).limit(limit)))
    return {
        "items": [site_response(site) for site in sites],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{site_id}", response_model=SiteResponse)
def get_site(site_id: str, _: CurrentUser, db: DbSession) -> dict[str, object]:
    return site_response(_site_or_404(db, site_id))


@router.get("/{site_id}/latest", response_model=LatestReadingResponse)
def get_latest_reading(site_id: str, _: CurrentUser, db: DbSession) -> dict[str, object]:
    _site_or_404(db, site_id)
    reading = db.scalar(
        select(Reading)
        .where(Reading.site_id == site_id)
        .order_by(Reading.measured_at.desc())
        .limit(1)
    )
    if reading is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No reading available for this site"
        )
    age_seconds = max(0, int((utc_now() - as_utc(reading.measured_at)).total_seconds()))
    return {
        "site_id": reading.site_id,
        "measured_at": utc_iso(reading.measured_at),
        "consumption_kwh": reading.consumption_kwh,
        "consumption_kwh_raw": reading.consumption_kwh_raw,
        "is_imputed": reading.is_imputed,
        "imputation_method": reading.imputation_method,
        "temperature_celsius": reading.temperature_celsius,
        "humidity_percent": reading.humidity_percent,
        "data_quality": reading.data_quality,
        "null_reasons": reading.null_reasons,
        "ingested_at": utc_iso(reading.ingested_at),
        "age_seconds": age_seconds,
    }
