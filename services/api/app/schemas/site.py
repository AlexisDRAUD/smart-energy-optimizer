from pydantic import BaseModel, ConfigDict, Field


class SiteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    city: str
    country: str
    surface_m2: float
    subscribed_power_kw: float


class SiteCreate(BaseModel):
    code: str = Field(min_length=2, max_length=20, pattern=r"^[A-Z0-9-]+$")
    name: str = Field(min_length=2, max_length=120)
    city: str = Field(min_length=2, max_length=100)
    country: str = Field(default="France", min_length=2, max_length=100)
    surface_m2: float = Field(gt=0)
    subscribed_power_kw: float = Field(gt=0)