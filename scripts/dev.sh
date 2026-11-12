#!/usr/bin/env bash
# Start the two development services; a single Ctrl+C stops both on macOS/Linux.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
PYTHON_BIN="${1:-backend/.venv/bin/python}"
NPM_BIN="${2:-npm}"
backend_pid=""
frontend_pid=""
# Enable job control for isolated background process groups (including on macOS).
set -m
cleanup() {
  trap - EXIT INT TERM
  for pid in "$backend_pid" "$frontend_pid"; do
    if [[ -n "$pid" ]]; then
      kill -TERM -- "-$pid" 2>/dev/null || true
      kill -TERM "$pid" 2>/dev/null || true
    fi
  done
  for pid in "$backend_pid" "$frontend_pid"; do
    if [[ -n "$pid" ]]; then wait "$pid" 2>/dev/null || true; fi
  done
}
trap cleanup EXIT INT TERM
"$PYTHON_BIN" -m uvicorn app.main:app --app-dir backend --reload --reload-dir backend/app --host 127.0.0.1 --port 8000 &
backend_pid=$!
(cd frontend && exec "$NPM_BIN" run dev) &
frontend_pid=$!
printf '\nNOVA Commerce (development):\n  App: http://localhost:5173\n  API: http://localhost:8000/docs\n  Ctrl+C stops both services.\n\n'
# Portable with macOS's system bash 3.2 (which has no `wait -n`).
while kill -0 "$backend_pid" 2>/dev/null && kill -0 "$frontend_pid" 2>/dev/null; do
  sleep 1
done
printf 'One development service exited; stopping the other.\n' >&2
exit 1
