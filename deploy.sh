#!/usr/bin/env bash
set -Eeuo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
command -v docker >/dev/null 2>&1 || fail 'Docker is not installed. Install Docker Engine and Compose v2 using official instructions; this script does not install them.'
docker info >/dev/null 2>&1 || fail 'Docker engine unavailable or permission denied. Check docker info / your Docker context. Do not chmod the Docker socket.'
[[ "$(docker info --format '{{.OSType}}')" == linux ]] || fail 'A Linux Docker engine is required.'
docker compose version >/dev/null 2>&1 || fail 'Docker Compose v2 is required.'
docker compose up --help | grep -q -- '--wait-timeout' || fail 'Upgrade Compose v2: up --wait-timeout support is required.'
# Separate config: never read/write the source/Windows .env.
if [[ ! -e .env.linux ]]; then
  (umask 077; set -o noclobber; cp -n .env.linux.example .env.linux)
fi
[[ -f .env.linux && ! -L .env.linux ]] || fail '.env.linux must be a regular non-symlink file.'
dc=(docker compose --env-file .env.linux -f compose.yaml)
trap 'rc=$?; printf "Deployment failed (exit %s). Diagnostics:\n" "$rc" >&2; "${dc[@]}" ps >&2 || true; "${dc[@]}" logs --tail=80 app >&2 || true; exit "$rc"' ERR
"${dc[@]}" config --quiet
# Build first: a build failure must not stop an already-running installation.
"${dc[@]}" build --pull app
"${dc[@]}" up -d --wait --wait-timeout 180 app
"${dc[@]}" exec -T app python -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8765/',timeout=5); assert r.status==200 and b'<html' in r.read().lower(); print('Homepage OK')"
printf 'StudyMind is healthy. Published endpoint: '
"${dc[@]}" port app 8765
printf 'Register your own account; there is no default password. See docs/LINUX.md.\n'
