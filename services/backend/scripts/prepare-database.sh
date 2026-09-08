#!/usr/bin/env sh
# Prepare la base pour tous les conteneurs du backend : schema Alembic, comptes
# de demonstration, puis reprise de l historique depuis la source. Les sites et
# les mesures transformees ne sont pas inseres ici, ils viennent de l ETL.
# Lance une fois par le service "migrate" du docker-compose, qui
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

printf '%s\n' 'Creation des comptes de demonstration...'
python -m app.db.seed

# Reprise de l historique des sites qui n ont pas encore le leur. Le module
# saute ceux qui l ont deja : l endpoint historique regenere les donnees a
# chaque appel, reprendre deux fois le meme site melangerait deux generations.
#
# Il sort en erreur des qu un site echoue, sinon une reprise partielle passerait
# pour une reussite. Rien n est perdu : un site en echec n a laisse aucune
# ligne, le prochain demarrage le reprend tout seul.
#
# L echec est volontairement non bloquant ici. Les conteneurs api, etl et
# collector attendent que celui-ci se termine SANS ERREUR : une source
# injoignable laisserait sinon toute la pile a l arret, alors qu un historique
# manquant n empeche ni le collecteur ni le dashboard de fonctionner.
printf '%s\n' 'Reprise de l historique...'
if ! python -m app.collector.backfill; then
  printf '%s\n' 'Reprise incomplete. Le collecteur prend le relais en temps reel,' >&2
  printf '%s\n' 'les sites manquants seront repris au prochain demarrage.' >&2
fi

printf '%s\n' 'Base prete.'
