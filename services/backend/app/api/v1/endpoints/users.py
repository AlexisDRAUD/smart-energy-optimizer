from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import AdminUser, DbSession
from app.api.v1.serializers import user_response
from app.crud.user import create_user
from app.db.models.user import User
from app.schemas.contract import IdentityResponse, UserCreate, UsersResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=UsersResponse)
def list_users(
    _: AdminUser,
    db: DbSession,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    total = db.scalar(select(func.count(User.id))) or 0
    users = list(db.scalars(select(User).order_by(User.email).offset(offset).limit(limit)))
    return {
        "items": [user_response(user) for user in users],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("", response_model=IdentityResponse, status_code=status.HTTP_201_CREATED)
def create_account(_: AdminUser, user_in: UserCreate, db: DbSession) -> dict[str, object]:
    try:
        return user_response(create_user(db, user_in))
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists"
        ) from error


@router.patch("/{user_id}", response_model=IdentityResponse)
def update_account(
    user_id: int,
    _: AdminUser,
    user_in: UserUpdate,
    db: DbSession,
) -> dict[str, object]:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    for field, value in user_in.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user_response(user)
