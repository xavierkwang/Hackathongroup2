#!/usr/bin/env bash
# Run the API (port 8787) and the web app (port 5173) locally. No AWS account needed.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pip install -q tzdata >/dev/null 2>&1 || true
python3 backend/local_server.py "$@" &
API_PID=$!
trap 'kill $API_PID 2>/dev/null' EXIT
(cd frontend && { [ -d node_modules ] || npm install; } && npm run dev)
