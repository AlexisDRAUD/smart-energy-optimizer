from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReadingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    site_id: int
    recorded_at: datetime
    consumption_kwh_raw: float | None
    consumption_kwh_imputed: float | None
    data_quality: str
    null_reasons: list[str] | None
    source: str


class ReadingCreate(BaseModel):
    recorded_at: datetime
    consumption_kwh_raw: float | None = Field(default=None, ge=0)
    consumption_kwh_imputed: float | None = Field(default=None, ge=0)
    data_quality: str = Field(default="good", pattern=r"^(good|partial|degraded|critical)$")
    null_reasons: list[str] | None = None

    @model_validator(mode="after")
    def validate_missing_value_traceability(self) -> "ReadingCreate":
        if self.consumption_kwh_raw is None and not self.null_reasons:
            raise ValueError("null_reasons is required when consumption_kwh_raw is null")
        if self.consumption_kwh_raw is not None and self.null_reasons:
            raise ValueError("null_reasons must be absent when consumption_kwh_raw is present")
        return self