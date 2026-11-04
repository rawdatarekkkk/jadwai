#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -f .env ]; then
  python3 -c 'import secrets; from pathlib import Path; p=Path(".env"); p.write_text("DATABASE_URL=postgresql+psycopg://mizan:mizan_local@127.0.0.1:5440/mizan\nJADWAI_ADMIN_EMAIL=admin@jadwai.local\nJADWAI_ADMIN_PASSWORD="+secrets.token_urlsafe(18)+"\n"); p.chmod(0o600)'
fi
set -a
source .env
set +a
docker compose -p mizan up -d --wait
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.lock.txt
(cd frontend && npm ci --no-audit --no-fund)
(cd backend && export DATABASE_URL="${DATABASE_ADMIN_URL:-$DATABASE_URL}" && .venv/bin/python -m alembic upgrade head && .venv/bin/python -m app.seed && .venv/bin/python -m app.provision)
echo 'Setup complete. Account details are in .env. Run bash scripts/dev.sh.'
