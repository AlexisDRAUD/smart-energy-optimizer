#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_ROOT"

PROFILE=${1:-${APP_PROFILE:-dev}}

case "$PROFILE" in
  dev|cloud)
    ;;
  *)
    printf '%s\n' "Profil inconnu : ${PROFILE}. Utilisez 'dev' ou 'cloud'." >&2
    exit 2
    ;;
esac

if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

if [ "$PROFILE" = "dev" ]; then
  DATABASE_URL=${DEV_DATABASE_URL:-sqlite:///./enervision.db}
  export DATABASE_URL
else
  if [ -f .env.cloud ]; then
    set -a
    . ./.env.cloud
    set +a
  fi

  : "${DATABASE_URL:?DATABASE_URL must be set for the cloud profile}"
  case "$DATABASE_URL" in
    postgresql://*|postgresql+psycopg://*)
      ;;
    *)
      printf '%s\n' 'Le profil cloud exige une URL PostgreSQL dans DATABASE_URL.' >&2
      exit 1
      ;;
  esac
fi

PYTHON=${PYTHON:-python3}
if [ -x .venv/bin/python ]; then
  PYTHON=.venv/bin/python
fi

repair_stale_dev_database() {
  if [ "$PROFILE" != "dev" ] || [ "$DATABASE_URL" != "sqlite:///./enervision.db" ] || [ ! -f enervision.db ]; then
    return
  fi

  revision=$(
    "$PYTHON" - <<'PY'
import sqlite3

connection = sqlite3.connect("enervision.db")
try:
    print(connection.execute("SELECT version_num FROM alembic_version").fetchone()[0])
except sqlite3.OperationalError as error:
    if "no such table" not in str(error):
        raise
finally:
    connection.close()
PY
  )

  if [ "$revision" = "20260902_0003" ]; then
    backup="enervision.db.stale-alembic-$(date +%Y%m%d%H%M%S)"
    printf '%s\n' "La base locale utilise une revision Alembic abandonnee. Sauvegarde : ${backup}"
    mv enervision.db "$backup"
  fi
}

prepare_cloud_database() {
  if [ "$PROFILE" != "cloud" ]; then
    return
  fi

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

repair_stale_dev_database
prepare_cloud_database

printf '%s\n' 'Application des migrations...'
"$PYTHON" -m alembic upgrade head

PORT=${PORT:-8080}
printf '%s\n' "Demarrage de l API sur http://localhost:${PORT}"
if [ "$PROFILE" = "dev" ]; then
  exec "$PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --reload
fi
exec "$PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
