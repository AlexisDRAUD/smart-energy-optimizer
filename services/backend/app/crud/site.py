from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.site import Site


def get_sites(db: Session) -> list[Site]:
    return list(db.scalars(select(Site).order_by(Site.site_name)))


def get_site(db: Session, site_id: str) -> Site | None:
    return db.get(Site, site_id)
