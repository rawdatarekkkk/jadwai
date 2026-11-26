#!/usr/bin/env bash
# Build and start JadwAI on the server. Safe to run again after every code update.
# First run: restores the demo database from deploy/data/demo.dump, if present.
# Usage on the server: bash ~/jadwai/deploy/server-up.sh <public-ip>
set -euo pipefail
cd "$(dirname "$0")"
umask 077
if [ ! -f .env ]; then
  ip="${1:?Give the server's public IP address the first time}"
  echo "SITE=${ip//./-}.sslip.io" > .env
  echo "DB_OWNER_PASSWORD=$(openssl rand -hex 24)" >> .env
fi
set -a; . ./.env; set +a
[ -f runtime.env ] || echo "DATABASE_URL=postgresql+psycopg://jadwai_owner:${DB_OWNER_PASSWORD}@db:5432/jadwai" > runtime.env
touch api.env worker.env

docker compose build
docker compose up -d --wait db

if [ -f data/demo.dump ] && [ ! -f data/.restored ]; then
  echo "Restoring the demo database"
  docker compose exec -T db pg_restore -U jadwai_owner -d jadwai --no-owner --no-acl --exit-on-error /restore/demo.dump
  touch data/.restored
fi

docker compose run --rm migrate
docker compose run --rm provision
# Runtime roles: the API and the worker never see the owner password.
grep '^DATABASE_URL=' runtime.env > api.env
grep '^WORKER_DATABASE_URL=' runtime.env | sed 's/^WORKER_DATABASE_URL=/DATABASE_URL=/' > worker.env

docker compose up -d --remove-orphans api worker web
echo "Waiting for the site"
for i in $(seq 1 60); do
  if curl -fsS --resolve "${SITE}:443:127.0.0.1" "https://${SITE}/api/health" 2>/dev/null | grep -q '"ready"'; then echo "Up: https://${SITE}"; exit 0; fi
  sleep 5
done
echo "Not ready yet; check: docker compose logs --tail 50" >&2
exit 1
