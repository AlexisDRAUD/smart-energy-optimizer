#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_ROOT"

if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

PYTHON=${PYTHON:-python3}
if [ -x .venv/bin/python ]; then
  PYTHON=.venv/bin/python
fi

printf '%s\n' 'Application des migrations...'
"$PYTHON" -m alembic upgrade head

printf '%s\n' 'Demarrage de l API sur http://localhost:8000'
exec "$PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --reload
