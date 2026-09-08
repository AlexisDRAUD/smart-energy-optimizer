from sqlalchemy import create_engine, text


class PostgresStorage:
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url)

    def ping(self) -> bool:
        with self.engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).fetchone()
        return result == (1,)

    def store_raw(self, source: str, payload: str) -> int:
        """Insere une mesure brute. Retourne 1 si inseree, 0 si deja presente."""
        with self.engine.begin() as conn:
            result = conn.execute(
                text(
                    "INSERT INTO raw_readings (source, payload) "
                    "VALUES (:source, :payload) "
                    "ON CONFLICT (site_id, measured_at) DO NOTHING"
                ),
                {"source": source, "payload": payload},
            )
            return result.rowcount

    def close(self) -> None:
        self.engine.dispose()
