from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.api.deps import CurrentUser, DbSession
from app.core.contract import require_utc_range, utc_now
from app.db.models.site import Site
from app.schemas.contract import ConsumptionChartResponse
from app.services.consumption_chart_service import MAX_DAYS, consumption_chart

router = APIRouter(prefix="/consumption-chart", tags=["dashboard"])


@router.get("", response_model=ConsumptionChartResponse)
def get_consumption_chart(
    request: Request,
    site_id: str,
    start: str,
    end: str,
    _: CurrentUser,
    db: DbSession,
) -> dict:
    # The existing access policy permits every authenticated user to read all sites.
    # Do not accept limit/offset or model overrides that could silently change this contract.
    if set(request.query_params) - {"site_id", "start", "end"}:
        raise HTTPException(422, "Only site_id, start and end are supported")
    start_at, end_at = require_utc_range(start, end)
    if end_at - start_at > timedelta(days=MAX_DAYS):
        raise HTTPException(422, "Chart history must not exceed 30 days")
    if end_at > utc_now():
        raise HTTPException(422, "Chart history end must not be in the future")
    if db.get(Site, site_id) is None:
        raise HTTPException(404, "Site not found")
    try:
        # Transaction-local bound: a sparse model version must not cause an unbounded scan.
        db.execute(text("SET LOCAL statement_timeout = '5s'"))
        return consumption_chart(db, site_id, start_at, end_at)
    except DBAPIError as error:
        if getattr(error.orig, "sqlstate", None) == "57014":
            db.rollback()
            raise HTTPException(
                503, "Chart query timed out; retry with a shorter window"
            ) from error
        raise
