#!/bin/sh
set -eu

lockfile_hash_file="node_modules/.tap-package-lock.hash"
next_binary="node_modules/next/package.json"
desired_hash="$(sha256sum package-lock.json | awk '{print $1}')"
current_hash=""

if [ -f "${lockfile_hash_file}" ]; then
  current_hash="$(cat "${lockfile_hash_file}")"
fi

if [ ! -f "${next_binary}" ] || [ "${current_hash}" != "${desired_hash}" ]; then
  echo "Installing web dependencies because node_modules is missing or package-lock changed."
  npm install
  mkdir -p node_modules
  printf '%s' "${desired_hash}" > "${lockfile_hash_file}"
else
  echo "Reusing existing web dependencies."
fi

exec npm run dev -- --hostname 0.0.0.0 --port 3000
