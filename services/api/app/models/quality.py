from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SensorStatus(Base):
    __tablename__ = "sensor_status"
    __table_args__ = (
        CheckConstraint(
            "sensor IN ('consumption', 'electrical', 'temperature', 'humidity', 'network')",
            name="ck_sensor_status_sensor",
        ),
        CheckConstraint("status IN ('ok', 'failing')", name="ck_sensor_status_status"),
        UniqueConstraint(
            "site_id", "sensor", "observed_at", name="uq_sensor_status_site_sensor_observed"
        ),
    )

    site_id: Mapped[str] = mapped_column(String, primary_key=True)
    sensor: Mapped[str] = mapped_column(String, primary_key=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    failing_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EtlRun(Base):
    __tablename__ = "etl_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'ok', 'partial', 'failed')",
            name="ck_etl_runs_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rows_read: Mapped[int] = mapped_column(Integer, nullable=False)
    rows_written: Mapped[int] = mapped_column(Integer, nullable=False)
    rows_imputed: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)


class DataQualityDaily(Base):
    __tablename__ = "data_quality_daily"
    __table_args__ = (UniqueConstraint("site_id", "day", name="uq_data_quality_daily_site_day"),)

    site_id: Mapped[str] = mapped_column(String, primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    expected_points: Mapped[int] = mapped_column(Integer, nullable=False)
    received_points: Mapped[int] = mapped_column(Integer, nullable=False)
    missing_points: Mapped[int] = mapped_column(Integer, nullable=False)
    null_points: Mapped[int] = mapped_column(Integer, nullable=False)
    imputed_points: Mapped[int] = mapped_column(Integer, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
