from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession, SiteUser
from app.crud.site import get_site
from app.services.prediction_service import predict_next_consumption

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("/sites/{site_id}/next")
def get_next_prediction(site_id: int, _: SiteUser, db: DbSession) -> dict[str, float | int]:
    if get_site(db, site_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    try:
        return predict_next_consumption(db, site_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
