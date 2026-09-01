from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.crud.user import get_user_by_username
from app.db.session import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/token")
DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(db: DbSession, token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        username = payload.get("sub")
    except jwt.InvalidTokenError as error:
        raise credentials_exception from error
    if not isinstance(username, str):
        raise credentials_exception

    user = get_user_by_username(db, username)
    if user is None or not user.is_active:
        raise credentials_exception
    return user


class RoleChecker:
    def __init__(self, *allowed_roles: str) -> None:
        self.allowed_roles = set(allowed_roles)

    def __call__(self, user: Annotated[User, Depends(get_current_user)]) -> User:
        user_roles = {role.name for role in user.roles}
        if not self.allowed_roles.intersection(user_roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user


CurrentUser = Annotated[User, Depends(get_current_user)]