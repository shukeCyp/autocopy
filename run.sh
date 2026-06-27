#!/usr/bin/env bash
set -e
export UV_INDEX_URL="${UV_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
export UV_DEFAULT_INDEX="${UV_DEFAULT_INDEX:-$UV_INDEX_URL}"

uv venv .venv --python "${PYTHON:-python3}"
UV_PROJECT_ENVIRONMENT=.venv uv sync

exec .venv/bin/python -m app.main
