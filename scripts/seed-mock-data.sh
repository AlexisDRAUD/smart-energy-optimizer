#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_ROOT"

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  printf '%s\n' 'Docker Compose est requis pour inserer les donnees mock.' >&2
  exit 1
fi

if [ "${MOCK_DATA_CONFIRM:-}" != "1" ]; then
  printf '%s\n' 'Le seed remplace les donnees des sites mock LYO-01, GRE-01 et NAN-01.' >&2
  printf '%s\n' 'Relancez avec MOCK_DATA_CONFIRM=1 pour confirmer.' >&2
  exit 1
fi

./scripts/verify-postgres-init.sh

printf '%s\n' 'Insertion des donnees mock...'
docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  < db/seeds/001_mock_data.sql
