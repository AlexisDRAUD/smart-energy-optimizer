"""Base declarative et connexion PostgreSQL partagees.

Le schema de la base est decrit par les modeles de app.db.models et par eux seuls.
Les migrations de services/backend/alembic/ les suivent.

Seul le backend touche a la base. Le ML la lit en SQL direct, il n importe pas ces modeles.
"""

from collections.abc import Generator

from app.config import settings
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def verify_database_connection() -> None:
    """Leve une exception quand la base configuree ne repond pas."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
