#!/usr/bin/env sh
# Prepare la base pour tous les conteneurs du backend : schema puis donnees de
# demonstration. Lance une fois par le service "migrate" du docker-compose, qui
# s arrete ensuite. Les autres conteneurs attendent qu il se termine sans erreur.
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_ROOT"

printf '%s\n' 'Attente de PostgreSQL...'
DATABASE_WAIT_SECONDS=${DATABASE_WAIT_SECONDS:-30}
attempt=0
until python -c 'from app.db.session import verify_database_connection; verify_database_connection()' >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge "$DATABASE_WAIT_SECONDS" ]; then
    printf '%s\n' "PostgreSQL ne repond pas apres ${DATABASE_WAIT_SECONDS} secondes." >&2
    exit 1
  fi
  sleep 1
done

printf '%s\n' 'Application des migrations Alembic...'
python -m alembic upgrade head

if [ "${SEED_DEMO_DATA:-0}" = "1" ]; then
  printf '%s\n' 'Insertion des donnees de demonstration...'
  python -m app.db.seed
else
  printf '%s\n' 'SEED_DEMO_DATA different de 1 : aucune donnee de demonstration inseree.'
fi

printf '%s\n' 'Base prete.'
