#!/usr/bin/env bash
# Stop the ED Simulator and keep all data:  ./stop.sh
# (Never use "docker compose down -v" before a session: it deletes the database.)
set -euo pipefail
cd "$(dirname "$0")"
docker compose --profile ollama down
