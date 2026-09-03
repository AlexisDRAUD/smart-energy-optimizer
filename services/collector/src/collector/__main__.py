from collector.config import db_config, source_api_url
from collector.loop import Collector
from collector.storage import PostgresStorage

if __name__ == "__main__":
    storage = PostgresStorage(**db_config())
    collector = Collector(5, source_api_url(), storage)
    collector.run()
