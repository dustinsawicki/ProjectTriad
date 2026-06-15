#!/usr/bin/env sh
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
RESEED=0
if [ "${1:-}" = "--reseed" ]; then RESEED=1; fi

echo "[run-seed] Reading azd env values ..."
eval "$(azd env get-values --output sh)"
export SQL_SERVER_FQDN SQL_DATABASE_NAME
export RESEED=$RESEED

if [ -z "${SQL_SERVER_FQDN:-}" ] || [ -z "${SQL_DATABASE_NAME:-}" ]; then
  echo "SQL_SERVER_FQDN / SQL_DATABASE_NAME not in azd env. Did 'azd provision' complete?" >&2
  exit 1
fi

echo "[run-seed] Target: $SQL_SERVER_FQDN / $SQL_DATABASE_NAME  (RESEED=$RESEED)"
python -m pip install --quiet -r "$HERE/requirements.txt"
python "$HERE/seed.py"
