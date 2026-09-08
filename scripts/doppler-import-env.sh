#!/usr/bin/env bash
set -euo pipefail

# Import .env into Doppler and optionally delete local .env after backup.
# Usage: ./scripts/doppler-import-env.sh [-p project] [-c config] [--delete] [--yes]

usage(){ cat <<EOF
Usage: $0 [-p project] [-c config] [--delete] [--yes]

Upload variables from .env to Doppler.

Options:
  -p, --project   Doppler project name (default: basename of repo directory)
  -c, --config    Doppler config name (default: dev)
  --delete        Delete .env after successful upload (backup created)
  --yes           Non-interactive: assume yes to confirmations
  -h, --help      Show this help
EOF
}

PROJECT=""
CONFIG=""
DELETE=0
YES=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--project)
      PROJECT="$2"; shift 2;;
    -c|--config)
      CONFIG="$2"; shift 2;;
    --delete)
      DELETE=1; shift;;
    --yes)
      YES=1; shift;;
    -h|--help)
      usage; exit 0;;
    *)
      echo "Unknown argument: $1"; usage; exit 1;;
  esac
done

ENV_FILE=".env"

if [ ! -f "$ENV_FILE" ]; then
  echo "Error: $ENV_FILE not found in $(pwd)"
  exit 1
fi

# defaults
if [ -z "$PROJECT" ]; then
  PROJECT=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
fi
if [ -z "$CONFIG" ]; then
  CONFIG="dev"
fi

if ! command -v doppler >/dev/null 2>&1; then
  echo "Error: doppler CLI not found. Install it from https://cli.doppler.com/"
  exit 1
fi

# check auth
if ! doppler whoami >/dev/null 2>&1; then
  if [ -z "${DOPPLER_TOKEN:-}" ]; then
    echo "Error: doppler not logged in and DOPPLER_TOKEN not set. Run 'doppler login' or export DOPPLER_TOKEN."
    exit 1
  fi
fi

# count keys (simple heuristic: lines matching KEY=)
SECRETS_COUNT=$(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$ENV_FILE" | wc -l | tr -d ' ')
if [ "$SECRETS_COUNT" -eq 0 ]; then
  echo "No secrets found in $ENV_FILE (no KEY= lines). Nothing to upload."
  exit 0
fi

echo "Preparing to upload $SECRETS_COUNT entries from $ENV_FILE to Doppler project='$PROJECT' config='$CONFIG'."

if [ "$YES" -eq 0 ]; then
  read -r -p "Proceed? (y/N): " ans
  case "${ans}" in
    [Yy]*) ;;
    *) echo "Aborted by user."; exit 1;;
  esac
fi

BACKUP_FILE=".env.doppler.backup.$(date +%Y%m%d%H%M%S)"
cp "$ENV_FILE" "$BACKUP_FILE"
echo "Backed up $ENV_FILE -> $BACKUP_FILE"

# Perform upload. Capture output to a temp file and do not print secret values.
TMPLOG=$(mktemp)
set +x
if doppler secrets upload --project "$PROJECT" --config "$CONFIG" "$ENV_FILE" >"$TMPLOG" 2>&1; then
  echo "Doppler upload succeeded."
else
  echo "Doppler upload failed. See $TMPLOG for details (sensitive values redacted below)."
  # Show log but redact anything that looks like KEY=VALUE
  sed -n '1,200p' "$TMPLOG" | sed -E 's/(\b[A-Za-z_][A-Za-z0-9_]*=).*/\1[REDACTED]/g'
  exit 1
fi
set -x

# Optionally delete .env (after backup)
if [ "$DELETE" -eq 1 ]; then
  if [ "$YES" -eq 0 ]; then
    read -r -p "Delete $ENV_FILE from disk now? (backup at $BACKUP_FILE) (y/N): " ans
    case "${ans}" in
      [Yy]*) ;;
      *) echo "Keeping $ENV_FILE"; exit 0;;
    esac
  fi
  rm -f "$ENV_FILE"
  echo "Removed $ENV_FILE (backup: $BACKUP_FILE)."
fi

# clean temp
rm -f "$TMPLOG"

echo "Done."
exit 0
