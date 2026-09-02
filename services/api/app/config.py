from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "EnerVision API"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./enervision.db"
    jwt_secret_key: str = "change-this-development-key-before-deployment"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    seed_user_password: str = "EnerVisionDemo2026!"
    prediction_refresh_interval_seconds: int = 60
    local_model_name: str = "local-moving-average"
    local_model_version: str = "local-1"


settings = Settings()