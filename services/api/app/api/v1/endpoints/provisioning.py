from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import DbSession, require_provisioning_key
from app.crud.site import create_site
from app.schemas.site import SiteCreate, SiteRead

router = APIRouter(
    prefix="/provisioning",
    tags=["provisioning"],
    dependencies=[Depends(require_provisioning_key)],
)


@router.post("/sites", response_model=SiteRead, status_code=status.HTTP_201_CREATED)
def create_new_site(db: DbSession, site_in: SiteCreate) -> SiteRead:
    try:
        return create_site(db, site_in)
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Site code already exists") from error
