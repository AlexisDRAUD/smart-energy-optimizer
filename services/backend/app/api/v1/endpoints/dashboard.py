from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.core.contract import SENSORS, require_utc_range, utc_iso, utc_now
from app.db.models.quality import DataQualityDaily, EtlRun, SensorStatus
from app.db.models.reading import Reading
from app.db.models.site import Site
from app.schemas.contract import (
    OverviewResponse,
    QualityResponse,
    RecommendationsResponse,
    SensorStatusResponse,
    StatusResponse,
)

router = APIRouter(tags=["dashboard"])


def _site_or_404(db: DbSession, site_id: str) -> Site:
    site = db.get(Site, site_id)
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    return site


@router.get("/overview", response_model=OverviewResponse)
def overview(_: CurrentUser, db: DbSession) -> dict[str, object]:
    by_site = []
    without_reading = []
    for site in db.scalars(select(Site).order_by(Site.site_name)):
        latest = db.scalar(
            select(Reading)
            .where(
                Reading.site_id == site.site_id,
                Reading.consumption_kwh.is_not(None),
                Reading.data_quality != "critical",
            )
            .order_by(Reading.measured_at.desc())
            .limit(1)
        )
        if latest is None or latest.consumption_kwh is None:
            without_reading.append(site.site_id)
            continue
        consumption = latest.consumption_kwh
        by_site.append(
            {
                "site_id": site.site_id,
                "consumption_kw": round(consumption, 3),
                "capacity_kw": site.capacity_kw,
                "load_rate_percent": round(consumption / site.capacity_kw * 100, 2),
                "measured_at": utc_iso(latest.measured_at),
            }
        )
    total_consumption = round(sum(site["consumption_kw"] for site in by_site), 3)
    total_capacity = round(sum(site["capacity_kw"] for site in by_site), 3)
    return {
        "site_count": db.scalar(select(func.count(Site.site_id))) or 0,
        "total_consumption_kw": total_consumption,
        "total_capacity_kw": total_capacity,
        "average_load_rate_percent": round(total_consumption / total_capacity * 100, 2)
        if total_capacity
        else 0.0,
        "by_site": by_site,
        "sites_without_valid_reading": without_reading,
        "sites_without_valid_reading_count": len(without_reading),
        "incomplete": bool(without_reading),
    }


@router.get("/quality", response_model=QualityResponse)
def quality(
    site_id: str,
    _: CurrentUser,
    db: DbSession,
    start: str | None = None,
    end: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    _site_or_404(db, site_id)
    now = utc_now()
    start_at, end_at = require_utc_range(
        start,
        end,
        default_start=now - timedelta(days=7),
        default_end=now,
    )
    end_day = (
        end_at.date() - timedelta(days=1) if end_at.time() == datetime.min.time() else end_at.date()
    )
    statement = (
        select(DataQualityDaily)
        .where(
            DataQualityDaily.site_id == site_id,
            DataQualityDaily.day >= start_at.date(),
            DataQualityDaily.day <= end_day,
        )
        .order_by(DataQualityDaily.day)
    )
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    records = list(db.scalars(statement.offset(offset).limit(limit)))
    return {
        "site_id": site_id,
        "start": utc_iso(start_at),
        "end": utc_iso(end_at),
        "points": [
            {
                "day": record.day.isoformat(),
                "expected_points": record.expected_points,
                "received_points": record.received_points,
                "missing_points": record.missing_points,
                "null_points": record.null_points,
                "imputed_points": record.imputed_points,
                "computed_at": utc_iso(record.computed_at),
            }
            for record in records
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/quality/sensors", response_model=SensorStatusResponse)
def sensor_quality(
    _: CurrentUser,
    db: DbSession,
    site_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    if site_id is not None:
        sites = [_site_or_404(db, site_id)]
    else:
        sites = list(db.scalars(select(Site).order_by(Site.site_name)))
    total = len(sites)
    response_sites = []
    for site in sites[offset : offset + limit]:
        sensor_points = []
        for sensor in SENSORS:
            observation = db.scalar(
                select(SensorStatus)
                .where(SensorStatus.site_id == site.site_id, SensorStatus.sensor == sensor)
                .order_by(SensorStatus.observed_at.desc())
                .limit(1)
            )
            sensor_points.append(
                {
                    "sensor": sensor,
                    "observed_at": utc_iso(observation.observed_at) if observation else None,
                    "status": observation.status if observation else "failing",
                    "failing_until": utc_iso(observation.failing_until) if observation else None,
                }
            )
        response_sites.append(
            {
                "site_id": site.site_id,
                "sensors": sensor_points,
                "overall": "failing"
                if any(sensor["status"] == "failing" for sensor in sensor_points)
                else "ok",
            }
        )
    return {"items": response_sites, "total": total, "limit": limit, "offset": offset}


@router.get("/status", response_model=StatusResponse)
def service_status(_: CurrentUser, db: DbSession) -> dict[str, object]:
    latest_finished = db.scalar(
        select(EtlRun)
        .where(EtlRun.finished_at.is_not(None))
        .order_by(EtlRun.finished_at.desc())
        .limit(1)
    )
    last_success = db.scalar(
        select(EtlRun.finished_at)
        .where(EtlRun.status == "ok", EtlRun.finished_at.is_not(None))
        .order_by(EtlRun.finished_at.desc())
        .limit(1)
    )
    return {
        "source": {
            "status": "ok" if last_success is not None else "unknown",
            "last_successful_collection_at": utc_iso(last_success),
        },
        "etl": {
            "status": latest_finished.status if latest_finished else "unknown",
            "last_completed_at": utc_iso(latest_finished.finished_at) if latest_finished else None,
            "last_result": latest_finished.status if latest_finished else None,
        },
    }


@router.get("/recommendations", response_model=RecommendationsResponse)
def recommendations(
    site_id: str,
    _: CurrentUser,
    db: DbSession,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    site = _site_or_404(db, site_id)
    latest = db.scalar(
        select(Reading)
        .where(Reading.site_id == site_id, Reading.consumption_kwh.is_not(None))
        .order_by(Reading.measured_at.desc())
        .limit(1)
    )
    if latest is None or latest.consumption_kwh is None:
        return {
            "site_id": site_id,
            "recommendations": [],
            "total": 0,
            "limit": limit,
            "offset": offset,
        }
    load_rate = latest.consumption_kwh / site.capacity_kw
    savings_rate = 0.1 if load_rate >= 0.8 else 0.05
    action = (
        "Shift flexible load outside the peak period."
        if load_rate >= 0.8
        else "Schedule discretionary equipment during lower-load periods."
    )
    recommendation = {
        "action": action,
        "estimated_savings_kwh": round(latest.consumption_kwh * savings_rate, 3),
    }
    return {
        "site_id": site_id,
        "recommendations": [recommendation][offset : offset + limit],
        "total": 1,
        "limit": limit,
        "offset": offset,
    }
