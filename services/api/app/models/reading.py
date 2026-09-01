from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Reading(Base):
    __tablename__ = "readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumption_kwh_raw: Mapped[float | None] = mapped_column(Float, nullable=True)
    consumption_kwh_imputed: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_quality: Mapped[str] = mapped_column(String(20), default="good")
    null_reasons: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    source: Mapped[str] = mapped_column(String(30), default="seed")
    site: Mapped["Site"] = relationship(back_populates="readings")