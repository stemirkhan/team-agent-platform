#!/usr/bin/env sh
set -eu

load_env_file() {
  env_file="$1"

  if [ ! -f "${env_file}" ]; then
    return 0
  fi

  while IFS= read -r line || [ -n "${line}" ]; do
    case "${line}" in
      ""|\#*)
        continue
        ;;
    esac

    key="${line%%=*}"
    value="${line#*=}"
    if [ "${key}" = "${line}" ]; then
      continue
    fi

    if env | grep -q "^${key}="; then
      continue
    fi

    export "${key}=${value}"
  done < "${env_file}"
}

if [ ! -f .env ]; then
  cp .env.example .env
fi

if [ -z "${XDG_DATA_HOME:-}" ] || echo "${XDG_DATA_HOME}" | grep -q '/snap/code/'; then
  export XDG_DATA_HOME="${HOME}/.local/share"
fi

load_env_file .env

build_flag=""
if [ "${1:-}" = "--build" ]; then
  build_flag="--build"
elif ! podman image exists team-agent-platform_backend >/dev/null 2>&1 \
  || ! podman image exists team-agent-platform_web >/dev/null 2>&1; then
  build_flag="--build"
fi

exec podman-compose -f infra/compose/docker-compose.yml up -d ${build_flag}
