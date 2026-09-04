from typing import Annotated

import jwt
from fastapi import APIRouter, Cookie, HTTPException, Response, status

from app.api.deps import CurrentUser, DbSession
from app.api.v1.serializers import user_response
from app.config import settings
from app.core.security import (
    REFRESH_TYPE,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.crud.user import get_user_by_email
from app.db.models.user import User
from app.schemas.contract import IdentityResponse, LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "enervision_refresh_token"
# Le navigateur n envoie ce cookie qu aux routes d authentification. Les autres
# appels de l API ne le voient jamais, ils portent l access token en en-tete.
REFRESH_COOKIE_PATH = f"{settings.api_v1_prefix}/auth"


def _invalid_credentials(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _open_session(response: Response, user: User) -> TokenResponse:
    """Pose un refresh token neuf dans le cookie et renvoie un access token.

    Appele a la connexion et a chaque renouvellement : le refresh token tourne,
    celui qui vient d etre utilise n a plus cours.
    """
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=create_refresh_token(user.email),
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
    return TokenResponse(
        access_token=create_access_token(user.email, user.role),
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/login", response_model=TokenResponse)
def login(credentials: LoginRequest, db: DbSession, response: Response) -> TokenResponse:
    user = get_user_by_email(db, str(credentials.email))
    if (
        user is None
        or not user.is_active
        or not verify_password(credentials.password, user.password_hash)
    ):
        raise _invalid_credentials("Incorrect email or password")
    return _open_session(response, user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    db: DbSession,
    response: Response,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
) -> TokenResponse:
    """Rend un access token neuf tant que la session du navigateur est valide."""
    if refresh_token is None:
        raise _invalid_credentials("Missing session")
    try:
        email = decode_token(refresh_token, REFRESH_TYPE).get("sub")
    except jwt.InvalidTokenError as error:
        raise _invalid_credentials("Invalid or expired session") from error
    if not isinstance(email, str):
        raise _invalid_credentials("Invalid or expired session")

    user = get_user_by_email(db, email)
    if user is None or not user.is_active:
        raise _invalid_credentials("Invalid or expired session")
    return _open_session(response, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    """Efface le cookie de session. Sans lui le front ne peut plus renouveler."""
    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)


@router.get("/me", response_model=IdentityResponse)
def me(user: CurrentUser) -> dict[str, object]:
    return user_response(user)
