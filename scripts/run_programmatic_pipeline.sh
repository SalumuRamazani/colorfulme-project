#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SOURCE="${PROGRAMMATIC_CONTENT_SOURCE:-content/programmatic_content.csv}"
SHEET="${PROGRAMMATIC_CONTENT_SHEET:-content}"
OUTPUT="${PROGRAMMATIC_CONTENT_MANIFEST:-static/data/programmatic_content_manifest.json}"

echo "[ColorfulMe] Generating programmatic manifest"
echo "- source: $SOURCE"
echo "- sheet:  $SHEET"
echo "- output: $OUTPUT"

python3 scripts/generate_programmatic_content.py --source "$SOURCE" --sheet "$SHEET" --output "$OUTPUT"

echo "[ColorfulMe] Done"
