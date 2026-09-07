import logging

from app.collector.loop import Collector
from app.collector.storage import PostgresStorage
from app.config import settings

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    # httpx journalise chaque requete en INFO : 8 lignes par minute qui noieraient
    # le compte rendu du passage.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    storage = PostgresStorage(settings.database_url)
    collector = Collector(
        settings.collector_interval_seconds,
        settings.source_api_base_url,
        storage,
    )
    collector.run()
