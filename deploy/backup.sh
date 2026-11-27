#!/usr/bin/env bash
# Nightly database backup on the server (installed as a cron job by server-up.sh).
# Keeps the 14 newest dumps in ~/backups. Restore one with:
#   docker compose -f ~/jadwai/deploy/compose.yaml exec -T db pg_restore -U jadwai_owner -d jadwai --clean --if-exists < ~/backups/<file>.dump
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p "$HOME/backups"
chmod 700 "$HOME/backups"
file="$HOME/backups/jadwai-$(date -u +%Y%m%d-%H%M).dump"
docker compose exec -T db pg_dump -U jadwai_owner -Fc jadwai > "$file.part"
mv "$file.part" "$file"
ls -1t "$HOME"/backups/jadwai-*.dump | tail -n +15 | xargs -r rm -f
echo "$(date -u +%FT%TZ) backup $(basename "$file") $(du -h "$file" | cut -f1)"
