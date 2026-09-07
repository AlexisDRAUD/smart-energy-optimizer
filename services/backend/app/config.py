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

    # Adresse de l API du formateur, la source des mesures.
    source_api_base_url: str = "http://127.0.0.1:8000"

    # Collecteur
    collector_interval_seconds: int = 60
    backfill_days: int = 7

    # ETL
    etl_interval_seconds: int = 60
    etl_batch_size: int = 1000
    # Recouvrement de la fenetre de lecture du brut. Chaque passage repart un
    # peu avant la borne du precedent : une ligne inseree juste apres la lecture
    # n est donc pas manquee. Il doit couvrir la plus longue transaction
    # d ecriture, qui dure des millisecondes ici. Deux minutes laissent mille
    # fois la marge necessaire. Ce n est pas la fenetre de reparation, qui est
    # plus large et porte sur readings.
    etl_window_overlap_minutes: int = 2

    # Reparation des valeurs nulles, sur readings.
    # Profondeur revisitee a chaque passage : une valeur nulle se repare des que
    # la mesure suivante arrive, donc a la minute d apres.
    imputation_window_minutes: int = 30
    # Age au dela duquel le profil d imputation d un site est recalcule.
    imputation_profile_refresh_hours: int = 24

    prediction_refresh_interval_seconds: int = 60
    prediction_horizon_minutes: int = 120
    local_model_name: str = "local-moving-average"
    local_model_version: str = "local-1"


settings = Settings()
