#!/usr/bin/env bash
# One command to start the ED Simulator:  ./start.sh
# Optional:  ./start.sh --build   (rebuild images after code changes)
#            ./start.sh --no-ollama (skip the optional local-model service)
set -euo pipefail
cd "$(dirname "$0")"

BUILD=""; PROFILE="--profile ollama"
for a in "$@"; do
  case "$a" in
    --build) BUILD="--build" ;;
    --no-ollama) PROFILE="" ;;
    *) echo "Unknown option: $a"; exit 1 ;;
  esac
done

if ! docker info >/dev/null 2>&1; then
  if command -v colima >/dev/null 2>&1; then
    echo "Starting Colima..."; colima start
  else
    echo "Docker is not running. Start Docker Desktop and run this again."; exit 1
  fi
fi

echo "Starting the application..."
docker compose $PROFILE up -d $BUILD

echo -n "Waiting for the backend"
for _ in $(seq 1 60); do
  if curl -sf http://localhost:8000/api/health >/dev/null 2>&1; then
    echo; echo "Ready."
    echo "  App:      http://localhost:4200"
    echo "  API docs: http://localhost:8000/api/docs"
    echo "Sign in as demo_presenter (password from your .env)."
    exit 0
  fi
  echo -n "."; sleep 2
done
echo; echo "Backend not ready after 2 minutes. Run: docker compose ps   and   docker compose logs backend"
exit 1
