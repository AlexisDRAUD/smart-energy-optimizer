from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Reglages du backend.

    Un seul objet pour l API, le collecteur et l ETL : ils tournent dans des
    conteneurs separes mais partagent la meme base et le meme code.
    """

    # Un seul fichier d environnement pour tout le depot, celui de la racine.
    # ".env" couvre la commande lancee depuis la racine, "../../.env" celle
    # lancee depuis services/backend (alembic, pytest). Dans le conteneur
    # aucun des deux n existe : les variables viennent du bloc environment:
    # de docker-compose.yml.
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        extra="ignore",
    )

    app_name: str = "EnerVision API"
    api_v1_prefix: str = "/api/v1"

    database_url: str

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    # Le cookie de session n est envoye qu en HTTPS quand ce reglage est actif.
    # False en local (http://localhost), True derriere le domaine de production.
    cookie_secure: bool = False

    seed_user_password: str

    prediction_refresh_interval_seconds: int = 60
    local_model_name: str = "local-moving-average"
    local_model_version: str = "local-1"


settings = Settings()
