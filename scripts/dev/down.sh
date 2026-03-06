#!/usr/bin/env sh
set -eu

if [ -z "${XDG_DATA_HOME:-}" ] || echo "${XDG_DATA_HOME}" | grep -q '/snap/code/'; then
  export XDG_DATA_HOME="${HOME}/.local/share"
fi

exec podman-compose -f infra/compose/docker-compose.yml down
