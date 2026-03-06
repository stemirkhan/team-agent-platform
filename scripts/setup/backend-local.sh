#!/usr/bin/env sh
set -eu

cd apps/backend
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
