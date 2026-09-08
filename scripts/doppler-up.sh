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
  # Allow interactive/local doppler login (doppler login) or a machine token.
  if doppler whoami >/dev/null 2>&1; then
    echo "doppler CLI is logged in locally — using local session."
  else
    echo "DOPPLER_TOKEN not set and doppler CLI not logged in."
    echo "Run 'doppler login' or export DOPPLER_TOKEN to enable Doppler secrets."
    read -r -p "Continue without Doppler (compose will run without Doppler)? (y/N): " answer
    case "${answer}" in
      [Yy]*) echo "Proceeding without Doppler."; exec docker compose up --build ;;
      *) echo "Aborting."; exit 1;;
    esac
  fi
fi

echo "Starting docker compose with Doppler..."
# Use doppler to inject env vars into docker compose
exec doppler run -- docker compose up --build
