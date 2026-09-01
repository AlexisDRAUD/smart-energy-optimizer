from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import DbSession, RoleChecker
from app.crud.user import create_user, get_user_by_username, get_users
from app.schemas.user import UserCreate, UserRead

router = APIRouter(prefix="/users", tags=["users"])
require_admin = RoleChecker("admin")


@router.get("", response_model=list[UserRead], dependencies=[Depends(require_admin)])
def list_users(db: DbSession) -> list[UserRead]:
    return get_users(db)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin)])
def create_new_user(db: DbSession, user_in: UserCreate) -> UserRead:
    if get_user_by_username(db, user_in.username) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")
    try:
        return create_user(db, user_in)
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists") from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
