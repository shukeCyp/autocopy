#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

export UV_INDEX_URL="${UV_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
export UV_DEFAULT_INDEX="${UV_DEFAULT_INDEX:-$UV_INDEX_URL}"

if [ ! -d .venv ]; then
  uv venv .venv --python "${PYTHON:-python3}"
fi

if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:8799 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port 8799 is already in use. Stop the existing backend before running ./run.sh:" >&2
  lsof -nP -iTCP:8799 -sTCP:LISTEN >&2
  exit 1
fi

UV_PROJECT_ENVIRONMENT=.venv uv sync --frozen

if [ ! -d frontend/node_modules ]; then
  (cd frontend && npm ci)
fi

if [ ! -f frontend/dist/index.html ] || find \
  frontend/src \
  frontend/public \
  frontend/index.html \
  frontend/package.json \
  frontend/package-lock.json \
  frontend/tsconfig.json \
  frontend/tsconfig.app.json \
  frontend/tsconfig.node.json \
  frontend/vite.config.ts \
  -newer frontend/dist/index.html -print -quit | grep -q .; then
  (cd frontend && npm run build)
else
  echo "Frontend dist is up to date; skipping build."
fi

exec .venv/bin/python run.py
