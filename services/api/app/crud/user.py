from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.user import User
from app.schemas.contract import UserCreate


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def get_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.email)))


def create_user(db: Session, user_in: UserCreate) -> User:
    user = User(
        email=str(user_in.email).lower(),
        password_hash=get_password_hash(user_in.password),
        role=user_in.role,
        created_at=datetime.now(UTC),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
