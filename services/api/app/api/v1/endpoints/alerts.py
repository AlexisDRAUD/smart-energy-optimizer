from __future__ import annotations

from datetime import timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession, OperatorUser
from app.api.v1.serializers import alert_response
from app.core.contract import as_utc, require_utc_range, utc_iso, utc_now
from app.models.alert import Alert
from app.models.site import Site
from app.schemas.contract import AlertResponse, AlertsResponse, AlertSummaryResponse

router = APIRouter(prefix="/alerts", tags=["alerts"])

Severity = Literal["low", "medium", "high", "critical"]
AlertStatus = Literal["open", "acknowledged", "closed"]
AlertType = Literal["spike", "threshold", "anomaly", "outage", "sensor"]
Period = Literal["day", "week", "month"]


@router.get("", response_model=AlertsResponse)
def list_alerts(
    _: CurrentUser,
    db: DbSession,
    site_id: str | None = None,
    severity: Severity | None = None,
    status_filter: Annotated[AlertStatus | None, Query(alias="status")] = "open",
    type: AlertType | None = None,
    start: str | None = None,
    end: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    if site_id is not None and db.get(Site, site_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    now = utc_now()
    start_at, end_at = require_utc_range(
        start,
        end,
        default_start=now - timedelta(days=7),
        default_end=now,
    )
    statement = select(Alert).where(Alert.detected_at >= start_at, Alert.detected_at < end_at)
    if site_id is not None:
        statement = statement.where(Alert.site_id == site_id)
    if severity is not None:
        statement = statement.where(Alert.severity == severity)
    if status_filter is not None:
        statement = statement.where(Alert.status == status_filter)
    if type is not None:
        statement = statement.where(Alert.type == type)
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    alerts = list(
        db.scalars(statement.order_by(Alert.detected_at.desc()).offset(offset).limit(limit))
    )
    return {
        "items": [alert_response(alert) for alert in alerts],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/summary", response_model=AlertSummaryResponse)
def alert_summary(
    _: CurrentUser,
    db: DbSession,
    period: Period = "day",
) -> dict[str, object]:
    now = utc_now()
    period_start = (
        now
        - {
            "day": timedelta(days=1),
            "week": timedelta(days=7),
            "month": timedelta(days=30),
        }[period]
    )
    period_alerts = list(
        db.scalars(
            select(Alert)
            .where(Alert.detected_at >= period_start, Alert.detected_at < now)
            .order_by(Alert.detected_at)
        )
    )
    counts = {severity: 0 for severity in ("low", "medium", "high", "critical")}
    by_day: dict[str, int] = {}
    for alert in period_alerts:
        counts[alert.severity] += 1
        day = as_utc(alert.detected_at).date().isoformat()
        by_day[day] = by_day.get(day, 0) + 1
    return {
        "period": period,
        "start": utc_iso(period_start),
        "end": utc_iso(now),
        "total": sum(counts.values()),
        "by_severity": counts,
        "by_day": by_day,
    }


@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
def acknowledge_alert(alert_id: int, user: OperatorUser, db: DbSession) -> dict[str, object]:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    if alert.status == "closed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Closed alerts cannot be acknowledged"
        )
    if alert.status == "open":
        alert.status = "acknowledged"
        alert.acknowledged_at = utc_now()
        alert.acknowledged_by = user.id
        db.commit()
        db.refresh(alert)
    return alert_response(alert)
