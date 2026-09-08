#!/usr/bin/env bash
set -euo pipefail

# Entrypoint wrapper: if DOPPLER_TOKEN (or doppler auth) is available, run
# the command through 'doppler run' so secrets are injected. Otherwise run
# the command as-is so local .env / compose env vars still work.

if [ -n "${DOPPLER_TOKEN:-}" ]; then
  exec doppler run -- "$@"
else
  exec "$@"
fi
