#!/bin/bash
set -euo pipefail

export SESSION_SECRET="${SESSION_SECRET:-dev-secret-key-for-testing}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///colorfulme.db}"
export FLASK_ENV="development"
export DEBUG="true"
export PORT="5003"

echo "Starting ColorfulMe (dev) on http://127.0.0.1:5003"
python3 app.py
