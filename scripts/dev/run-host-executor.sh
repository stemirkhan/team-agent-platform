#!/usr/bin/env sh
set -eu

read_env_value() {
  key="$1"
  value=""

  if [ -f .env ]; then
    value="$(sed -n "s/^${key}=//p" .env | tail -n 1)"
  fi

  if [ -z "${value}" ] && [ -f .env.example ]; then
    value="$(sed -n "s/^${key}=//p" .env.example | tail -n 1)"
  fi

  if [ -z "${value}" ]; then
    return 0
  fi

  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"
  printf '%s' "${value}"
}

infer_bind_host() {
  base_url="$1"

  case "${base_url}" in
    ""|http://127.0.0.1:*|https://127.0.0.1:*|http://localhost:*|https://localhost:*)
      printf '%s' "127.0.0.1"
      ;;
    *)
      printf '%s' "0.0.0.0"
      ;;
  esac
}

infer_bind_port() {
  base_url="$1"

  case "${base_url}" in
    http://*:*|https://*:* )
      host_port="${base_url#http://}"
      host_port="${host_port#https://}"
      host_port="${host_port%%/*}"
      printf '%s' "${host_port##*:}"
      ;;
    *)
      printf '%s' "8765"
      ;;
  esac
}

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

host_executor_base_url="${HOST_EXECUTOR_BASE_URL:-$(read_env_value HOST_EXECUTOR_BASE_URL)}"
host_executor_host="${HOST_EXECUTOR_HOST:-$(read_env_value HOST_EXECUTOR_HOST)}"
host_executor_port="${HOST_EXECUTOR_PORT:-$(read_env_value HOST_EXECUTOR_PORT)}"

if [ -z "${host_executor_host}" ]; then
  host_executor_host="$(infer_bind_host "${host_executor_base_url}")"
fi

if [ -z "${host_executor_port}" ]; then
  host_executor_port="$(infer_bind_port "${host_executor_base_url}")"
fi

if [ "${HOST_EXECUTOR_RELOAD:-1}" = "1" ]; then
exec apps/backend/.venv/bin/python -m uvicorn host_executor_app.main:app \
  --host "${host_executor_host}" \
  --port "${host_executor_port}" \
  --reload
fi

exec apps/backend/.venv/bin/python -m uvicorn host_executor_app.main:app \
  --host "${host_executor_host}" \
  --port "${host_executor_port}"
