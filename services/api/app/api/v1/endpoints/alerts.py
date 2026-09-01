from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.alert import AlertRead
from app.services.alert_service import get_alerts

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertRead])
def list_alerts(_: CurrentUser, db: DbSession, active_only: bool = True) -> list[AlertRead]:
    return get_alerts(db, active_only)
