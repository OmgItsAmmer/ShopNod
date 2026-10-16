#!/bin/sh
# api container entrypoint: migrate (and seed the demo market in DEMO_MODE), then run the server.
set -e

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "[entrypoint] alembic upgrade head"
  alembic upgrade head
fi

if [ "${DEMO_MODE:-false}" = "true" ] && [ "${RUN_SEED:-true}" = "true" ]; then
  echo "[entrypoint] seeding templates, Demo Market and demo shops"
  python infra/seed/seed.py
fi

exec "$@"
