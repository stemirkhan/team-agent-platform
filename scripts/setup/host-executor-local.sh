#!/usr/bin/env sh
set -eu

if [ ! -x apps/backend/.venv/bin/python ]; then
  echo "Backend virtualenv not found." >&2
  echo "Create it first:" >&2
  echo "  cd apps/backend" >&2
  echo "  python3 -m venv .venv" >&2
  echo "  . .venv/bin/activate" >&2
  echo "  pip install -e '.[dev]'" >&2
  exit 1
fi

echo "Host executor will use apps/backend/.venv as its Python runtime."
