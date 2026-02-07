#!/bin/bash
set -euo pipefail

export SESSION_SECRET="${SESSION_SECRET:-dev-secret-key-for-testing}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///colorfulme.db}"
export FLASK_ENV="development"
export DEBUG="true"
export PORT="5003"
export LOCAL_DEV_AUTO_LOGIN="${LOCAL_DEV_AUTO_LOGIN:-true}"
export LOCAL_DEV_AUTO_LOGIN_EMAIL="${LOCAL_DEV_AUTO_LOGIN_EMAIL:-local-dev@colorfulme.app}"
export LOCAL_DEV_AUTO_LOGIN_NAME="${LOCAL_DEV_AUTO_LOGIN_NAME:-Local Dev}"
export LOCAL_DEV_UNLIMITED_CREDITS="${LOCAL_DEV_UNLIMITED_CREDITS:-true}"

echo "Starting ColorfulMe (dev) on http://127.0.0.1:5003"
python3 app.py
