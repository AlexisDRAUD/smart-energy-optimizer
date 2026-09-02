#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_ROOT"

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  printf '%s\n' 'Docker Compose est requis pour verifier PostgreSQL.' >&2
  exit 1
fi

printf '%s\n' 'Demarrage de PostgreSQL avec db/migrations/001_schema.sql...'
docker compose up -d db

attempt=0
until docker compose exec -T db sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    printf '%s\n' 'PostgreSQL ne repond pas apres 30 secondes.' >&2
    exit 1
  fi
  sleep 1
done

table_count=$(
  docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At' <<'SQL'
SELECT count(*)
FROM unnest(
    ARRAY[
        'raw_readings',
        'raw_snapshots',
        'sites',
        'readings',
        'sensor_status',
        'etl_runs',
        'data_quality_daily',
        'users',
        'predictions',
        'alerts'
    ]::text[]
) AS expected(table_name)
WHERE to_regclass('public.' || expected.table_name) IS NOT NULL;
SQL
)

if [ "$table_count" -ne 10 ]; then
  printf '%s\n' "Schema incomplet : ${table_count}/10 tables attendues sont presentes." >&2
  exit 1
fi

printf '%s\n' 'PostgreSQL est pret : 001_schema.sql a cree les 10 tables attendues.'
