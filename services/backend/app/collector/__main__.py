from app.collector.loop import Collector
from app.collector.storage import PostgresStorage
from app.config import settings

if __name__ == "__main__":
    storage = PostgresStorage(settings.database_url)
    collector = Collector(
        settings.collector_interval_seconds,
        settings.source_api_base_url,
        storage,
    )
    collector.run()
