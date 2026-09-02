from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import DbSession, require_provisioning_key
from app.crud.site import get_site
from app.crud.user import create_user, get_user_by_username, get_users
from app.schemas.user import UserCreate, UserRead

router = APIRouter(
    prefix="/provisioning/users",
    tags=["provisioning"],
    dependencies=[Depends(require_provisioning_key)],
)


@router.get("", response_model=list[UserRead])
def list_users(db: DbSession) -> list[UserRead]:
    return get_users(db)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_new_user(db: DbSession, user_in: UserCreate) -> UserRead:
    if get_user_by_username(db, user_in.username) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")
    if get_site(db, user_in.site_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    try:
        return create_user(db, user_in)
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists") from error
