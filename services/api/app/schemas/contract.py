from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

ISODateTime = str


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorDetail(ContractModel):
    code: str
    message: str


class ErrorResponse(ContractModel):
    error: ErrorDetail


class LoginRequest(ContractModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(ContractModel):
    access_token: str
    token_type: Literal["bearer"] = Field(default="bearer")
    expires_in: int = Field(gt=0)


class IdentityResponse(ContractModel):
    id: int
    email: EmailStr
    role: Literal["viewer", "operator", "admin"]
    is_active: bool
    created_at: ISODateTime = Field(json_schema_extra={"format": "date-time"})


class SiteResponse(ContractModel):
    site_id: str
    site_type: str
    site_name: str
    location: str
    capacity_kw: float
    status: Literal["active", "inactive"]
    last_seen_at: ISODateTime = Field(json_schema_extra={"format": "date-time"})


class SitesResponse(ContractModel):
    items: list[SiteResponse]
    total: int
    limit: int
    offset: int


class ReadingPoint(ContractModel):
    measured_at: ISODateTime = Field(json_schema_extra={"format": "date-time"})
    consumption_kwh: float | None
    is_imputed: bool
    data_quality: Literal["good", "partial", "degraded", "critical"]


class ReadingsCompleteness(ContractModel):
    expected_points: int = Field(ge=0)
    received_points: int = Field(ge=0)
    imputed_points: int = Field(ge=0)
    missing_points: int = Field(ge=0)
    percent: float = Field(ge=0, le=100)


class ReadingsResponse(ContractModel):
    site_id: str
    granularity: Literal["minute", "quarter", "hour", "day"]
    points: list[ReadingPoint]
    completeness: ReadingsCompleteness
    total: int = Field(ge=0)


class LatestReadingResponse(ReadingPoint):
    site_id: str
    consumption_kwh_raw: float | None
    imputation_method: str | None
    temperature_celsius: float | None
    humidity_percent: float | None
    null_reasons: list[str]
    ingested_at: ISODateTime = Field(json_schema_extra={"format": "date-time"})
    age_seconds: int = Field(ge=0)


class OverviewSite(ContractModel):
    site_id: str
    consumption_kw: float
    capacity_kw: float
    load_rate_percent: float
    measured_at: ISODateTime = Field(json_schema_extra={"format": "date-time"})


class OverviewResponse(ContractModel):
    site_count: int = Field(ge=0)
    total_consumption_kw: float = Field(ge=0)
    total_capacity_kw: float = Field(ge=0)
    average_load_rate_percent: float = Field(ge=0)
    by_site: list[OverviewSite]
    sites_without_valid_reading: list[str]
    sites_without_valid_reading_count: int = Field(ge=0)
    incomplete: bool


class QualityDailyPoint(ContractModel):
    day: str = Field(json_schema_extra={"format": "date"})
    expected_points: int
    received_points: int
    missing_points: int
    null_points: int
    imputed_points: int
    computed_at: ISODateTime = Field(json_schema_extra={"format": "date-time"})


class QualityResponse(ContractModel):
    site_id: str
    start: ISODateTime = Field(json_schema_extra={"format": "date-time"})
    end: ISODateTime = Field(json_schema_extra={"format": "date-time"})
    points: list[QualityDailyPoint]
    total: int = Field(ge=0)
    limit: int
    offset: int


class SensorPoint(ContractModel):
    sensor: Literal["consumption", "electrical", "temperature", "humidity", "network"]
    observed_at: ISODateTime | None = Field(default=None, json_schema_extra={"format": "date-time"})
    status: Literal["ok", "failing"]
    failing_until: ISODateTime | None = Field(
        default=None, json_schema_extra={"format": "date-time"}
    )


class SensorSiteResponse(ContractModel):
    site_id: str
    sensors: list[SensorPoint]
    overall: Literal["ok", "failing"]


class SensorStatusResponse(ContractModel):
    items: list[SensorSiteResponse]
    total: int
    limit: int
    offset: int


class AlertResponse(ContractModel):
    id: int
    site_id: str
    detected_at: ISODateTime = Field(json_schema_extra={"format": "date-time"})
    type: Literal["spike", "threshold", "anomaly", "outage", "sensor"]
    severity: Literal["low", "medium", "high", "critical"]
    message: str
    value: float | None
    threshold_value: float | None
    status: Literal["open", "acknowledged", "closed"]
    acknowledged_at: ISODateTime | None = Field(
        default=None, json_schema_extra={"format": "date-time"}
    )


class AlertsResponse(ContractModel):
    items: list[AlertResponse]
    total: int
    limit: int
    offset: int


class AlertSummaryResponse(ContractModel):
    period: Literal["day", "week", "month"]
    start: ISODateTime = Field(json_schema_extra={"format": "date-time"})
    end: ISODateTime = Field(json_schema_extra={"format": "date-time"})
    total: int
    by_severity: dict[str, int]
    by_day: dict[str, int]


class PredictionResponse(ContractModel):
    site_id: str
    predicted_at: ISODateTime = Field(json_schema_extra={"format": "date-time"})
    target_at: ISODateTime = Field(json_schema_extra={"format": "date-time"})
    horizon_minutes: int = Field(gt=0)
    predicted_kwh: float
    model_version: str
    actual_kwh: float | None
    absolute_error: float | None


class PredictionsResponse(ContractModel):
    items: list[PredictionResponse]
    total: int
    limit: int
    offset: int


class ModelResponse(ContractModel):
    model_name: str
    model_version: str
    trained_at: ISODateTime | None = Field(default=None, json_schema_extra={"format": "date-time"})
    horizon_minutes: int
    test_metrics: dict[str, float | None]
    availability: Literal["local_fallback", "mlflow"]
    mlflow_available: bool


class Metric(ContractModel):
    mae: float | None
    rmse: float | None
    mape_percent: float | None


class ModelPerformanceResponse(ContractModel):
    sample_size: int
    model: Metric
    persistence_baseline: Metric
    linear_baseline: Metric


class Recommendation(ContractModel):
    action: str
    estimated_savings_kwh: float = Field(ge=0)


class RecommendationsResponse(ContractModel):
    site_id: str
    recommendations: list[Recommendation]
    total: int
    limit: int
    offset: int


class SourceStatus(ContractModel):
    status: str
    last_successful_collection_at: ISODateTime | None = Field(
        default=None, json_schema_extra={"format": "date-time"}
    )


class EtlStatus(ContractModel):
    status: str
    last_completed_at: ISODateTime | None = Field(
        default=None, json_schema_extra={"format": "date-time"}
    )
    last_result: str | None


class StatusResponse(ContractModel):
    source: SourceStatus
    etl: EtlStatus


class UserCreate(ContractModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role: Literal["viewer", "operator", "admin"] = "viewer"


class UserUpdate(ContractModel):
    role: Literal["viewer", "operator", "admin"] | None = None
    is_active: bool | None = None


class UsersResponse(ContractModel):
    items: list[IdentityResponse]
    total: int
    limit: int
    offset: int
