#!/usr/bin/env bash
# Run on the Mac: copy the code (and, with --data, a cleaned copy of the local demo database and the
# v4 adapter) to the server, then build and start it there.
# Usage: bash deploy/push.sh <server-ip> [--data]
set -euo pipefail
cd "$(dirname "$0")/.."
ip="${1:?Give the server IP}"
key="$HOME/.ssh/jadwai_oracle"
ssh_cmd=(ssh -i "$key" -o StrictHostKeyChecking=accept-new "ubuntu@$ip")

if [ "${2:-}" = "--data" ]; then
  # Clean copy of the demo database: no sessions, reset links, sign-in counters or test-only accounts.
  mkdir -p deploy/data
  docker exec mizan-db-1 sh -c 'dropdb -U mizan --if-exists jadwai_deploy && createdb -U mizan jadwai_deploy && pg_dump -U mizan -Fc jadwai_demo | pg_restore -U mizan -d jadwai_deploy --no-owner --no-acl'
  docker exec -i mizan-db-1 psql -U mizan -d jadwai_deploy -v ON_ERROR_STOP=1 -q < deploy/clean-demo.sql
  docker exec mizan-db-1 pg_dump -U mizan -Fc jadwai_deploy > deploy/data/demo.dump
  docker exec mizan-db-1 dropdb -U mizan jadwai_deploy
  ls -la deploy/data/demo.dump
fi

rsync -az --delete -e "ssh -i $key" \
  --exclude node_modules --exclude dist --exclude .venv --exclude __pycache__ --exclude .pytest_cache \
  --exclude 'deploy/.env' --exclude 'deploy/*.env' --exclude 'deploy/data/.restored' \
  --include 'finetuning/' --include 'finetuning/*.sh' --include 'finetuning/*.py' \
  --include 'finetuning/models/' --include 'finetuning/models/jai-lora-v4.zip' \
  --exclude 'finetuning/models/llama.cpp-src/build' --include 'finetuning/models/llama.cpp-src/***' --exclude 'finetuning/**' \
  --include 'evaluation/' --include 'evaluation/***' \
  --include 'backend/***' --include 'worker/***' --include 'frontend/***' --include 'ops/***' --include 'deploy/***' \
  --include '.dockerignore' --exclude '*' \
  ./ "ubuntu@$ip:jadwai/"
"${ssh_cmd[@]}" "bash ~/jadwai/deploy/server-up.sh $ip"
