#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

export UV_INDEX_URL="${UV_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
export UV_DEFAULT_INDEX="${UV_DEFAULT_INDEX:-$UV_INDEX_URL}"

if [ ! -d .venv ]; then
  uv venv .venv --python "${PYTHON:-python3}"
fi

UV_PROJECT_ENVIRONMENT=.venv uv sync

if [ ! -d frontend/node_modules ]; then
  (cd frontend && npm ci)
fi

(cd frontend && npm run build)

exec .venv/bin/python run.py
