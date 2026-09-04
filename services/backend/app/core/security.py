from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.config import settings

password_hash = PasswordHash.recommended()

ACCESS_TYPE = "access"
REFRESH_TYPE = "refresh"


def verify_password(plain_password: str, password_hash_value: str) -> bool:
    return password_hash.verify(plain_password, password_hash_value)


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)


def _create_token(claims: dict[str, object], lifetime: timedelta) -> str:
    payload = {**claims, "exp": datetime.now(UTC) + lifetime}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str, role: str) -> str:
    """Jeton court presente a chaque appel de l API."""
    return _create_token(
        {"sub": subject, "role": role, "typ": ACCESS_TYPE},
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(subject: str) -> str:
    """Jeton long garde dans un cookie httpOnly, sert seulement a en obtenir un court."""
    return _create_token(
        {"sub": subject, "typ": REFRESH_TYPE},
        timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str, expected_type: str) -> dict[str, object]:
    """Decode un jeton et refuse un jeton dont le type ne correspond pas.

    Les deux jetons sont signes avec la meme cle. Sans cette verification, un
    refresh token presente en Authorization ferait office d access token et
    ouvrirait un acces valable plusieurs jours.
    """
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    if payload.get("typ") != expected_type:
        raise jwt.InvalidTokenError("Unexpected token type")
    return payload
