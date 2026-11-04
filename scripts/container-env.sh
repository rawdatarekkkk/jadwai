#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
backend/.venv/bin/python - <<'PY'
from pathlib import Path
from sqlalchemy.engine import make_url
p=Path('.env')
values=dict(line.split('=',1) for line in p.read_text().splitlines() if '=' in line and not line.startswith('#'))
for source,target in [('DATABASE_URL','APP_CONTAINER_DATABASE_URL'),('WORKER_DATABASE_URL','WORKER_CONTAINER_DATABASE_URL')]:
    url=make_url(values[source])
    values[target]=url.set(host='db',port=5432).render_as_string(hide_password=False)
p.write_text('\n'.join(f'{k}={v}' for k,v in values.items())+'\n')
p.chmod(0o600)
PY
