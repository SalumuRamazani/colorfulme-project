#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "Generating programmatic content manifest..."
"$PYTHON_BIN" scripts/generate_programmatic_content.py

echo "Done. Restart Flask to load latest manifest."
