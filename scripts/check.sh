#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
set -a
source .env
set +a
(cd backend && .venv/bin/python -m pytest -q)
backend/.venv/bin/python -m unittest discover -s evaluation/tests
(cd frontend && npm run build && npm test)
