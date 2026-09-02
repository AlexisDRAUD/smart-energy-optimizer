import psycopg


class PostgresStorage:
    def __init__(self, host: str, port: int, dbname: str, user: str, password: str):
        self.conn = psycopg.connect(
            host=host, port=port, dbname=dbname, user=user, password=password
        )

    def ping(self) -> bool:
        result = self.conn.execute("SELECT 1").fetchone()
        return result == (1,)

    def store_raw(self, source: str, payload: str) -> None:
        self.conn.execute(
            "INSERT INTO raw_readings (source, payload) VALUES (%s, %s)",
            (source, payload),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
