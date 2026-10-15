#!/usr/bin/env bash
# Runs the API (uvicorn) and the web server (nginx) side by side.
# If either exits, the other is stopped and the container exits with that
# status, so Docker's restart policy sees the failure.
set -euo pipefail

mkdir -p /tmp/nginx

# Every start is a fresh demo: clear old uploads, then rebuild the database
# with the seven demo leads. Runs before the API, since the reset deletes the
# database file. A failed seed is logged but never stops the app starting.
rm -rf data/uploads/*
python scripts/seed.py --reset || echo "[seed] demo data not loaded; starting anyway" >&2

# One worker on purpose: extraction runs as in-process background tasks and
# SQLite has a single writer.
uvicorn app.main:app --host 127.0.0.1 --port 8001 \
  --proxy-headers --forwarded-allow-ips 127.0.0.1 &
api_pid=$!

nginx -e /dev/stderr -c /app/nginx.conf -g 'daemon off;' &
web_pid=$!

shutdown() {
  kill -TERM "$api_pid" "$web_pid" 2>/dev/null || true
  wait || true
}
trap shutdown TERM INT

set +e
wait -n "$api_pid" "$web_pid"
status=$?
set -e
shutdown
exit "$status"
