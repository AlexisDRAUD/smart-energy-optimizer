from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.user import User
from app.schemas.user import UserCreate


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))


def get_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.username)))


def create_user(db: Session, user_in: UserCreate) -> User:
    user = User(
        username=user_in.username,
        email=str(user_in.email),
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
        site_id=user_in.site_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user