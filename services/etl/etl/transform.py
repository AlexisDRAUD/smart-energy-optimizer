"""Validation and normalization of source energy readings."""

import logging
import math
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, ValidationError, field_validator

LOGGER = logging.getLogger(__name__)

NUMERIC_FIELDS = (
    "consumption_kw",
    "consumption_kwh",
    "voltage_v",
    "current_a",
    "power_factor",
    "temperature_celsius",
    "humidity_percent",
)


class EnergyReading(BaseModel):
    """A validated reading plus an untouched copy of its source payload."""

    model_config = ConfigDict(extra="allow")

    timestamp: datetime
    site_id: str
    site_type: str
    consumption_kw: float | None = Field(default=None, ge=0)
    consumption_kwh: float | None = Field(default=None, ge=0)
    voltage_v: float | None = None
    current_a: float | None = None
    power_factor: float | None = Field(default=None, ge=0, le=1)
    temperature_celsius: float | None = None
    humidity_percent: float | None = Field(default=None, ge=0, le=100)
    null_reasons: list[str]
    data_quality: Literal["good", "partial", "degraded", "critical"]

    _source_payload: dict[str, Any] = PrivateAttr(default_factory=dict)

    @field_validator("timestamp", mode="before")
    @classmethod
    def validate_timestamp(cls, value: Any) -> datetime:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("timestamp doit être une date ISO sous forme de chaîne")

        normalized_value = f"{value[:-1]}+00:00" if value.endswith("Z") else value
        try:
            parsed_value = datetime.fromisoformat(normalized_value)
        except ValueError as exc:
            raise ValueError("timestamp doit être une date ISO valide") from exc

        if parsed_value.tzinfo is None:
            return parsed_value.replace(tzinfo=UTC)
        return parsed_value.astimezone(UTC)

    @field_validator("site_id", "site_type", mode="before")
    @classmethod
    def validate_non_empty_string(cls, value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("la valeur doit être une chaîne non vide")
        return value

    @field_validator(*NUMERIC_FIELDS, mode="before")
    @classmethod
    def normalize_number(cls, value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool):
            raise ValueError("une valeur booléenne n'est pas un nombre de mesure")
        try:
            normalized_value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("la valeur doit être convertible en nombre") from exc
        if not math.isfinite(normalized_value):
            raise ValueError("la valeur numérique doit être finie")
        return normalized_value

    @field_validator("null_reasons", mode="before")
    @classmethod
    def validate_null_reasons(cls, value: Any) -> list[Any]:
        if not isinstance(value, list):
            raise ValueError("null_reasons doit être une liste")
        return value

    @classmethod
    def from_source(cls, payload: Mapping[str, Any]) -> Self:
        reading = cls.model_validate(dict(payload))
        reading._source_payload = deepcopy(dict(payload))
        return reading

    @property
    def source_payload(self) -> dict[str, Any]:
        """Return an untouched copy used to trace missing and explicit null fields."""
        return deepcopy(self._source_payload)

    def normalized_payload(self) -> dict[str, Any]:
        """Return normalized fields while keeping absent source fields absent."""
        return self.model_dump(mode="json", exclude_unset=True)


@dataclass(frozen=True)
class TransformResult:
    readings: list[EnergyReading]
    rejected_count: int


def transform_readings(
    raw_readings: list[Any], logger: logging.Logger | None = None
) -> TransformResult:
    """Validate each row independently so one rejection does not stop the batch."""
    active_logger = logger or LOGGER
    valid_readings: list[EnergyReading] = []
    rejected_count = 0

    for row_number, raw_reading in enumerate(raw_readings, start=1):
        if not isinstance(raw_reading, Mapping):
            rejected_count += 1
            active_logger.warning("Ligne %d rejetée: un objet JSON est attendu", row_number)
            continue

        try:
            valid_readings.append(EnergyReading.from_source(raw_reading))
        except ValidationError as exc:
            rejected_count += 1
            active_logger.warning("Ligne %d rejetée: %s", row_number, exc)

    return TransformResult(readings=valid_readings, rejected_count=rejected_count)
