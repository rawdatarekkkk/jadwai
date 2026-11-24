#!/usr/bin/env bash
cd "$(dirname "$0")/../../.."
while pgrep -f eval-round4.sh >/dev/null; do sleep 60; done
echo "started: $(date)" >> thesis/evidence/2026-11-24-contract/RUN.txt
backend/.venv/bin/python thesis/evidence/2026-11-24-contract/score_contract_prompt.py --timeout 600
echo "finished: $(date)" >> thesis/evidence/2026-11-24-contract/RUN.txt
