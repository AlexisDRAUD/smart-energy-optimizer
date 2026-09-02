from __future__ import annotations

from datetime import datetime

from sqlalchemy import ARRAY, Boolean, CheckConstraint, DateTime, Float, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Reading(Base):
    __tablename__ = "readings"
    __table_args__ = (
        CheckConstraint(
            "data_quality IN ('good', 'partial', 'degraded', 'critical')",
            name="ck_readings_data_quality",
        ),
        UniqueConstraint("site_id", "measured_at", name="uq_readings_site_measured"),
    )

    site_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    measured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, index=True
    )
    consumption_kwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    consumption_kwh_raw: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_imputed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    imputation_method: Mapped[str | None] = mapped_column(String, nullable=True)
    temperature_celsius: Mapped[float | None] = mapped_column(Float, nullable=True)
    humidity_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_quality: Mapped[str] = mapped_column(String, nullable=False, default="good")
    null_reasons: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
