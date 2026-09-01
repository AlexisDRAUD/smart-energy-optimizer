from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "EnerVision API"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./enervision.db"
    jwt_secret_key: str = "change-this-development-key-before-deployment"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    seed_user_password: str = "EnerVisionDemo2026!"


settings = Settings()