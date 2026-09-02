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

printf '%s\n' 'Verification de la configuration...'
"$PYTHON" -c 'from app.config import settings'

printf '%s\n' 'Verification de l acces a la base de donnees...'
DATABASE_WAIT_SECONDS=${DATABASE_WAIT_SECONDS:-30}
attempt=0
until "$PYTHON" -c 'from app.db.session import verify_database_connection; verify_database_connection()' >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge "$DATABASE_WAIT_SECONDS" ]; then
    printf '%s\n' "Impossible de se connecter a la base apres ${DATABASE_WAIT_SECONDS} secondes." >&2
    printf '%s\n' 'Verifiez DATABASE_URL et demarrez PostgreSQL avant de relancer le script.' >&2
    exit 1
  fi
  sleep 1
done

printf '%s\n' 'Application des migrations...'
"$PYTHON" -m alembic upgrade head

PORT=${PORT:-8080}
printf '%s\n' "Demarrage de l API sur http://localhost:${PORT}"
exec "$PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --reload
