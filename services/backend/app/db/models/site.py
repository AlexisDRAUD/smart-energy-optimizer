from __future__ import annotations

from datetime import datetime

from app.db.session import Base
from sqlalchemy import CheckConstraint, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column


class Site(Base):
    __tablename__ = "sites"

    __table_args__ = (CheckConstraint("status IN ('active', 'inactive')", name="ck_sites_status"),)

    site_id: Mapped[str] = mapped_column(String, primary_key=True)
    site_type: Mapped[str] = mapped_column(String, nullable=False)
    site_name: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str] = mapped_column(String, nullable=False)
    capacity_kw: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
