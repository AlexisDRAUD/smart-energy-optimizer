#!/usr/bin/env sh
# Demarre l API. Le schema et les donnees de demonstration sont la responsabilite du
# service "migrate", qui tourne avant et s arrete.
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_ROOT"

: "${DATABASE_URL:?DATABASE_URL doit etre defini}"
case "$DATABASE_URL" in
  postgresql://*|postgresql+psycopg://*) ;;
  *)
    printf '%s\n' 'DATABASE_URL doit utiliser PostgreSQL.' >&2
    exit 1
    ;;
esac

PYTHON=${PYTHON:-python3}
if [ -x .venv/bin/python ]; then
  PYTHON=.venv/bin/python
fi

PORT=${PORT:-8080}
printf '%s\n' "Demarrage de l API sur http://localhost:${PORT}"
exec "$PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
