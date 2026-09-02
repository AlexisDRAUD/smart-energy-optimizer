from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.api.v1.serializers import user_response
from app.config import settings
from app.core.security import create_access_token, verify_password
from app.crud.user import get_user_by_email
from app.schemas.contract import IdentityResponse, LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(credentials: LoginRequest, db: DbSession) -> TokenResponse:
    user = get_user_by_email(db, str(credentials.email))
    if (
        user is None
        or not user.is_active
        or not verify_password(credentials.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(
        access_token=create_access_token(user.email, user.role),
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=IdentityResponse)
def me(user: CurrentUser) -> dict[str, object]:
    return user_response(user)
