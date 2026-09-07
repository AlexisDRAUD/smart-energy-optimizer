from collections.abc import Sequence

from sqlalchemy import create_engine, text

# Une mesure par site et par instant. La cle unique de raw_readings absorbe les
# doublons, ce qui rend le collecteur et la reprise d historique rejouables.
INSERT_RAW_READING = text(
    "INSERT INTO raw_readings (source, payload) "
    "VALUES (:source, :payload) "
    "ON CONFLICT (site_id, measured_at) DO NOTHING"
)

INSERT_RAW_SNAPSHOT = text("INSERT INTO raw_snapshots (source, payload) VALUES (:source, :payload)")

DEFAULT_BATCH_SIZE = 1000


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
            result = conn.execute(INSERT_RAW_READING, {"source": source, "payload": payload})
            return result.rowcount

    def store_raw_many(
        self, source: str, payloads: Sequence[str], batch_size: int = DEFAULT_BATCH_SIZE
    ) -> int:
        """Insere des mesures brutes par lots. Rend le nombre de lignes inserees.

        Une transaction par lot, et non une par ligne. La reprise d historique
        ecrit des dizaines de milliers de lignes : a raison d une transaction
        chacune, elle ne finirait pas.

        Les doublons sont ignores, comme dans store_raw. Le compte rendu ne
        porte donc que sur les lignes reellement ecrites, pas sur celles
        envoyees.
        """
        if not payloads:
            return 0

        inserted = 0
        with self.engine.begin() as conn:
            for start in range(0, len(payloads), batch_size):
                batch = payloads[start : start + batch_size]
                result = conn.execute(
                    INSERT_RAW_READING,
                    [{"source": source, "payload": payload} for payload in batch],
                )
                inserted += result.rowcount
        return inserted

    def store_snapshot(self, source: str, payload: str) -> None:
        """Enregistre un instantane du referentiel dans raw_snapshots.

        Pas de cle unique ici, volontairement : deux instantanes identiques a
        deux minutes d ecart sont deux faits distincts. C est ce qui permet de
        dire quand la source a change d avis sur un site ou un capteur.
        """
        with self.engine.begin() as conn:
            conn.execute(INSERT_RAW_SNAPSHOT, {"source": source, "payload": payload})

    def close(self) -> None:
        self.engine.dispose()
