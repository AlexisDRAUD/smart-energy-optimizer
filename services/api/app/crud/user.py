from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.security import get_password_hash
from app.models.user import Role, User
from app.schemas.user import UserCreate


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).options(selectinload(User.roles)).where(User.username == username))


def get_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).options(selectinload(User.roles)).order_by(User.username)))


def create_user(db: Session, user_in: UserCreate) -> User:
    roles = list(db.scalars(select(Role).where(Role.name.in_(user_in.role_names))))
    if len(roles) != len(set(user_in.role_names)):
        raise ValueError("One or more roles do not exist")

    user = User(
        username=user_in.username,
        email=str(user_in.email),
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
        roles=roles,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user