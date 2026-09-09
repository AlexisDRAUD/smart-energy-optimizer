"""Validation of alert snapshots returned by the source API."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

LOGGER = logging.getLogger(__name__)


class SourceAlert(BaseModel):
    """Canonical alert accepted by the transformed layer."""

    model_config = ConfigDict(extra="ignore")

    site_id: str
    detected_at: datetime
    type: Literal["spike", "threshold", "anomaly", "outage", "sensor"]
    severity: Literal["low", "medium", "high", "critical"]
    message: str
    value: float | None = None
    threshold_value: float | None = None
    status: Literal["open", "acknowledged", "closed"] = "open"

    @field_validator("detected_at", mode="before")
    @classmethod
    def normalize_timestamp(cls, value: Any) -> datetime:
        if not isinstance(value, str):
            raise ValueError("detected_at doit etre une date ISO")
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)

    @field_validator("site_id", "message", mode="before")
    @classmethod
    def non_empty(cls, value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("une chaine non vide est requise")
        return value.strip()


def _canonical_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    canonical = dict(payload)
    aliases = {
        "detected_at": ("timestamp", "triggered_at"),
        "type": ("alert_type",),
        "value": ("current_value", "consumption_kwh"),
        "threshold_value": ("threshold", "threshold_kwh"),
    }
    for target, candidates in aliases.items():
        if canonical.get(target) is None:
            canonical[target] = next(
                (canonical[name] for name in candidates if canonical.get(name) is not None), None
            )

    severity = str(canonical.get("severity", "")).lower()
    canonical["severity"] = {
        "info": "low",
        "warning": "medium",
        "warn": "medium",
        "danger": "high",
        "emergency": "critical",
    }.get(severity, severity)

    if canonical.get("status") is None:
        active = canonical.get("is_active", canonical.get("active"))
        if isinstance(active, bool):
            canonical["status"] = "open" if active else "closed"
    status = str(canonical.get("status", "open")).lower()
    canonical["status"] = {
        "active": "open",
        "resolved": "closed",
        "inactive": "closed",
    }.get(status, status)
    return canonical


def transform_alert_snapshot(
    payload: Any, logger: logging.Logger | None = None
) -> tuple[list[SourceAlert], int]:
    """Accept a list or an API envelope and reject malformed items independently."""
    active_logger = logger or LOGGER
    items = payload.get("items", payload.get("alerts")) if isinstance(payload, Mapping) else payload
    if not isinstance(items, list):
        active_logger.warning("Instantane api_alerts rejete: tableau ou enveloppe attendu")
        return [], 1

    alerts: list[SourceAlert] = []
    rejected = 0
    for index, item in enumerate(items, start=1):
        if not isinstance(item, Mapping):
            rejected += 1
            active_logger.warning("Alerte source %d rejetee: objet attendu", index)
            continue
        try:
            alerts.append(SourceAlert.model_validate(_canonical_payload(item)))
        except (ValidationError, ValueError) as error:
            rejected += 1
            active_logger.warning("Alerte source %d rejetee: %s", index, error)
    return alerts, rejected
