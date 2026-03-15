#!/usr/bin/env sh
set -eu

if [ ! -x apps/backend/.venv/bin/python ]; then
  echo "Backend virtualenv not found." >&2
  echo "Run ./scripts/setup/host-executor-local.sh for prerequisites." >&2
  exit 1
fi

# Native CLI installers such as Claude Code commonly register binaries via
# ~/.local/bin or the helper env script generated there. The host executor is
# often launched from tmux/non-login shells, so make sure those paths exist.
if [ -f "${HOME}/.local/bin/env" ]; then
  # shellcheck disable=SC1090
  . "${HOME}/.local/bin/env"
elif [ -d "${HOME}/.local/bin" ]; then
  export PATH="${HOME}/.local/bin:${PATH}"
fi

export PYTHONPATH="$(pwd)/apps/host-executor"

if [ "${HOST_EXECUTOR_RELOAD:-1}" = "1" ]; then
exec apps/backend/.venv/bin/python -m uvicorn host_executor_app.main:app \
  --host "${HOST_EXECUTOR_HOST:-0.0.0.0}" \
  --port "${HOST_EXECUTOR_PORT:-8765}" \
  --reload
fi

exec apps/backend/.venv/bin/python -m uvicorn host_executor_app.main:app \
  --host "${HOST_EXECUTOR_HOST:-0.0.0.0}" \
  --port "${HOST_EXECUTOR_PORT:-8765}"
