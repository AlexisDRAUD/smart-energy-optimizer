from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.site import Site
from app.schemas.site import SiteCreate


def get_sites(db: Session) -> list[Site]:
    return list(db.scalars(select(Site).order_by(Site.name)))


def get_site(db: Session, site_id: int) -> Site | None:
    return db.get(Site, site_id)


def create_site(db: Session, site_in: SiteCreate) -> Site:
    site = Site(**site_in.model_dump())
    db.add(site)
    db.commit()
    db.refresh(site)
    return site