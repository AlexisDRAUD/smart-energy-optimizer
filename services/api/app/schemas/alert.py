from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    site_id: int
    severity: str
    message: str
    triggered_at: datetime
    is_active: bool


class AlertCreate(BaseModel):
    severity: str = Field(pattern=r"^(info|warning|critical)$")
    message: str = Field(min_length=3, max_length=255)