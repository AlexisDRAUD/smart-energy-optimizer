from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.config import settings

password_hash = PasswordHash.recommended()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)


def create_access_token(subject: str, roles: list[str]) -> str:
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "roles": roles, "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)