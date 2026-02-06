#!/bin/bash
set -euo pipefail

export FLASK_APP=app.py
export SESSION_SECRET="${SESSION_SECRET:-dev-secret-key-for-testing}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///colorfulme.db}"
export FLASK_ENV="${FLASK_ENV:-development}"
export DEBUG="${DEBUG:-true}"
export PORT="${PORT:-5003}"

echo "Starting ColorfulMe on http://127.0.0.1:${PORT}"
python3 app.py
