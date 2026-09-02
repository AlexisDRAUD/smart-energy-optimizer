#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_ROOT"

if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

if [ -z "${DATABASE_URL:-}" ]; then
  DATABASE_URL=$(sed -n 's/^[[:space:]]*sqlalchemy.url[[:space:]]*=[[:space:]]*//p' alembic.ini | head -n 1)
  export DATABASE_URL
fi

PYTHON=${PYTHON:-python3}
if [ -x .venv/bin/python ]; then
  PYTHON=.venv/bin/python
fi

printf '%s\n' 'Verification de l acces a la base de donnees...'
"$PYTHON" -c 'from app.db.session import verify_database_connection; verify_database_connection()'

printf '%s\n' 'Application des migrations...'
"$PYTHON" -m alembic upgrade head

printf '%s\n' 'Demarrage de l API sur http://localhost:8080'
exec "$PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}" --reload
