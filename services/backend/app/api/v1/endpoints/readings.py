from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.contract import QUALITY_ORDER, as_utc, require_utc_range, utc_iso, utc_now
from app.db.models.reading import Reading
from app.db.models.site import Site
from app.schemas.contract import ReadingsResponse

router = APIRouter(prefix="/readings", tags=["readings"])

Granularity = Literal["minute", "quarter", "hour", "day"]
_INTERVALS = {
    "minute": timedelta(minutes=1),
    "quarter": timedelta(minutes=15),
    "hour": timedelta(hours=1),
    "day": timedelta(days=1),
}


def _site_or_404(db: DbSession, site_id: str) -> None:
    if db.get(Site, site_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")


def _bucket(value: datetime, granularity: Granularity) -> datetime:
    value = as_utc(value)
    if granularity == "minute":
        return value.replace(second=0, microsecond=0)
    if granularity == "quarter":
        return value.replace(minute=value.minute - value.minute % 15, second=0, microsecond=0)
    if granularity == "hour":
        return value.replace(minute=0, second=0, microsecond=0)
    return value.replace(hour=0, minute=0, second=0, microsecond=0)


@router.get("", response_model=ReadingsResponse)
def list_readings(
    site_id: str,
    _: CurrentUser,
    db: DbSession,
    start: str | None = None,
    end: str | None = None,
    granularity: Granularity = "minute",
    limit: int = Query(default=1000, ge=1, le=10_000),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    _site_or_404(db, site_id)
    default_end = utc_now()
    start_at, end_at = require_utc_range(
        start,
        end,
        default_start=default_end - timedelta(days=1),
        default_end=default_end,
    )
    readings = list(
        db.scalars(
            select(Reading)
            .where(
                Reading.site_id == site_id,
                Reading.measured_at >= start_at,
                Reading.measured_at < end_at,
            )
            .order_by(Reading.measured_at)
        )
    )

    buckets: dict[datetime, list[Reading]] = {}
    for reading in readings:
        buckets.setdefault(_bucket(reading.measured_at, granularity), []).append(reading)

    points = []
    for measured_at, source_points in sorted(buckets.items()):
        values = [
            point.consumption_kwh for point in source_points if point.consumption_kwh is not None
        ]
        quality = max(
            source_points, key=lambda point: QUALITY_ORDER[point.data_quality]
        ).data_quality
        points.append(
            {
                "measured_at": utc_iso(measured_at),
                "consumption_kwh": round(sum(values), 3) if values else None,
                "is_imputed": any(point.is_imputed for point in source_points),
                "data_quality": quality,
            }
        )

    interval = _INTERVALS[granularity]
    first_bucket = _bucket(start_at, granularity)
    last_bucket = _bucket(end_at - timedelta(microseconds=1), granularity)
    expected_points = int((last_bucket - first_bucket) / interval) + 1
    received_points = len(points)
    imputed_points = sum(point["is_imputed"] for point in points)
    completeness = {
        "expected_points": expected_points,
        "received_points": received_points,
        "imputed_points": imputed_points,
        "missing_points": max(0, expected_points - received_points),
        "percent": round(received_points / expected_points * 100, 2) if expected_points else 100.0,
    }
    return {
        "site_id": site_id,
        "granularity": granularity,
        "points": points[offset : offset + limit],
        "completeness": completeness,
        "total": len(points),
    }
