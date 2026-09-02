from sqlalchemy import create_engine, text


class PostgresStorage:
    def __init__(self, host: str, port: int, dbname: str, user: str, password: str):
        url = f"postgresql+psycopg://{user}:{password}@{host}:{port}/{dbname}"
        self.engine = create_engine(url)

    def ping(self) -> bool:
        with self.engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).fetchone()
        return result == (1,)

    def store_raw(self, source: str, payload: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO raw_readings (source, payload) VALUES (:source, :payload)"),
                {"source": source, "payload": payload},
            )

    def close(self) -> None:
        self.engine.dispose()
