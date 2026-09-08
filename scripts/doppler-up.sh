#!/usr/bin/env bash
set -euo pipefail

# Lightweight helper to start the stack with Doppler providing secrets.
# Usage:
#   ./scripts/doppler-up.sh

if ! command -v doppler >/dev/null 2>&1; then
  echo "doppler CLI not found. Install it: https://cli.doppler.com/"
  exit 1
fi

if [ -z "${DOPPLER_TOKEN:-}" ]; then
  echo "DOPPLER_TOKEN not set. You can run 'doppler login' interactively or export DOPPLER_TOKEN."
  echo "If you want to proceed without Doppler, set DOPPLER_TOKEN= and run 'docker compose up' directly."
  read -r -p "Continue without Doppler token? (y/N): " answer
  case "${answer}" in
    [Yy]*) ;;
    *) echo "Aborting."; exit 1;;
  esac
fi

echo "Starting docker compose with Doppler..."
# Use doppler to inject env vars into docker compose
exec doppler run -- docker compose up --build
