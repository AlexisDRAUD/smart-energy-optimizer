from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status

QUALITY_ORDER = {"good": 0, "partial": 1, "degraded": 2, "critical": 3}
SENSORS = ("consumption", "electrical", "temperature", "humidity", "network")


def utc_now() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    """Normalise database values; SQLite returns naive values for timezone columns."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return as_utc(value).isoformat().replace("+00:00", "Z")


def parse_utc(value: str, field_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{field_name} must be an ISO-8601 UTC timestamp",
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{field_name} must be an ISO-8601 UTC timestamp",
        )
    return parsed.astimezone(UTC)


def require_utc_range(
    start: str | None,
    end: str | None,
    *,
    default_start: datetime | None = None,
    default_end: datetime | None = None,
) -> tuple[datetime, datetime]:
    start_at = parse_utc(start, "start") if start else default_start
    end_at = parse_utc(end, "end") if end else default_end
    if start_at is None or end_at is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="start and end are required ISO-8601 UTC timestamps",
        )
    if end_at <= start_at:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="end must be later than start",
        )
    return start_at, end_at
