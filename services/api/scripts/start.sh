#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_ROOT"

if [ "${1:-cloud}" != "cloud" ]; then
  printf '%s\n' "Profil inconnu : ${1}. Utilisez 'cloud'." >&2
  exit 2
fi

: "${DATABASE_URL:?DATABASE_URL must be set}"
case "$DATABASE_URL" in
  postgresql://*|postgresql+psycopg://*)
    ;;
  *)
    printf '%s\n' 'DATABASE_URL doit utiliser PostgreSQL.' >&2
    exit 1
    ;;
esac

PYTHON=${PYTHON:-python3}
if [ -x .venv/bin/python ]; then
  PYTHON=.venv/bin/python
fi

prepare_database() {
  schema_state=$(
    "$PYTHON" - <<'PY'
from sqlalchemy import inspect

from app.db.base import Base
from app.db.session import engine
import app.models  # noqa: F401

with engine.connect() as connection:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    expected_tables = set(Base.metadata.tables)

    if "alembic_version" in tables:
        print("versioned")
    elif not expected_tables.intersection(tables):
        print("empty")
    elif all(
        table_name in tables
        and set(Base.metadata.tables[table_name].columns.keys()).issubset(
            {column["name"] for column in inspector.get_columns(table_name)}
        )
        for table_name in expected_tables
    ):
        print("contract")
    else:
        print("unknown")
PY
  )

  case "$schema_state" in
    empty|versioned)
      ;;
    contract)
      printf '%s\n' 'Schema cloud contractuel detecte sans historique Alembic : initialisation du suivi.'
      "$PYTHON" -m alembic stamp head
      ;;
    *)
      printf '%s\n' 'Le schema cloud ne correspond ni au contrat attendu ni a un historique Alembic.' >&2
      printf '%s\n' 'Aucune migration automatique n a ete appliquee.' >&2
      exit 1
      ;;
  esac
}

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

prepare_database

printf '%s\n' 'Application des migrations...'
"$PYTHON" -m alembic upgrade head

PORT=${PORT:-8080}
printf '%s\n' "Demarrage de l API sur http://localhost:${PORT}"
exec "$PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
