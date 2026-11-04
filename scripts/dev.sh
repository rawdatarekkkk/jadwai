#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
set -a
source .env
set +a
ROOT_DIR="$PWD"
pids=()
cleanup() { for process_id in "${pids[@]}"; do kill "$process_id" 2>/dev/null || true; done; }
trap cleanup EXIT INT TERM
(cd backend && unset DATABASE_ADMIN_URL WORKER_DATABASE_URL APP_CONTAINER_DATABASE_URL WORKER_CONTAINER_DATABASE_URL JADWAI_ADMIN_PASSWORD && exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8010) &
pids+=("$!")
(cd backend && export DATABASE_URL="${WORKER_DATABASE_URL:-$DATABASE_URL}" && unset OPENAI_API_KEY DATABASE_ADMIN_URL WORKER_DATABASE_URL APP_CONTAINER_DATABASE_URL WORKER_CONTAINER_DATABASE_URL JADWAI_ADMIN_PASSWORD && export PYTHONPATH="$PWD" && exec .venv/bin/python "$ROOT_DIR/worker/main.py") &
pids+=("$!")
(cd frontend && unset OPENAI_API_KEY DATABASE_URL DATABASE_ADMIN_URL WORKER_DATABASE_URL APP_CONTAINER_DATABASE_URL WORKER_CONTAINER_DATABASE_URL JADWAI_ADMIN_PASSWORD && exec node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5180 --strictPort) &
pids+=("$!")
echo 'JadwAI: http://127.0.0.1:5180 — API: http://127.0.0.1:8010/docs'
wait
