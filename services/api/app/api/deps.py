from secrets import compare_digest
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status
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


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_provisioning_key(
    provisioning_key: Annotated[str | None, Header(alias="X-Provisioning-Key")] = None,
) -> None:
    if provisioning_key is None or not compare_digest(provisioning_key, settings.provisioning_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid provisioning key")


def require_site_access(site_id: int, user: CurrentUser) -> User:
    if user.site_id != site_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to this site is forbidden")
    return user


SiteUser = Annotated[User, Depends(require_site_access)]