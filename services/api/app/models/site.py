from __future__ import annotations

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    city: Mapped[str] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(100), default="France")
    surface_m2: Mapped[float] = mapped_column(Float)
    subscribed_power_kw: Mapped[float] = mapped_column(Float)
    readings: Mapped[list["Reading"]] = relationship(back_populates="site", cascade="all, delete-orphan")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="site", cascade="all, delete-orphan")