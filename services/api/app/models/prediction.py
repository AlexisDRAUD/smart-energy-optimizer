from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Computed, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint(
            "site_id",
            "target_at",
            "model_version",
            "horizon_minutes",
            name="uq_predictions_site_target_model_horizon",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    site_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    target_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    horizon_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    model_name: Mapped[str] = mapped_column(String, nullable=False)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    predicted_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    actual_kwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    absolute_error: Mapped[float | None] = mapped_column(
        Float,
        Computed("CASE WHEN actual_kwh IS NULL THEN NULL ELSE abs(predicted_kwh - actual_kwh) END"),
        nullable=True,
    )
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
