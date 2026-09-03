from app.collector.config import database_url, source_api_url
from app.collector.loop import Collector
from app.collector.storage import PostgresStorage

if __name__ == "__main__":
    storage = PostgresStorage(database_url())
    collector = Collector(60, source_api_url(), storage)
    collector.run()
