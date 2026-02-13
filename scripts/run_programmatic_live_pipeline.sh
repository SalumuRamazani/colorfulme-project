#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SOURCE="${PROGRAMMATIC_CONTENT_SOURCE:-content/programmatic_content.csv}"
SHEET="${PROGRAMMATIC_CONTENT_SHEET:-content}"
MODE="${PIPELINE_MODE:-all}"
BATCH_ID="${BATCH_ID:-batch-$(date -u +%Y%m%d%H%M%S)}"
LIMIT="${LIMIT:-0}"
DRY_RUN="${DRY_RUN:-false}"
FORCE_CONTENT="${FORCE_CONTENT:-false}"
FORCE_IMAGES="${FORCE_IMAGES:-false}"
FILTER_EXPR="${FILTER_EXPR:-}"

FILL_ARGS=(
  --source "$SOURCE"
  --sheet "$SHEET"
  --mode "$MODE"
  --batch-id "$BATCH_ID"
)

if [[ "$LIMIT" != "0" ]]; then
  FILL_ARGS+=(--limit "$LIMIT")
fi
if [[ "$DRY_RUN" == "true" ]]; then
  FILL_ARGS+=(--dry-run)
fi
if [[ "$FORCE_CONTENT" == "true" ]]; then
  FILL_ARGS+=(--force-content)
fi
if [[ "$FORCE_IMAGES" == "true" ]]; then
  FILL_ARGS+=(--force-images)
fi
if [[ -n "$FILTER_EXPR" ]]; then
  FILL_ARGS+=(--filter "$FILTER_EXPR")
fi

echo "[ColorfulMe] Programmatic live pipeline"
echo "- source: $SOURCE"
echo "- sheet: $SHEET"
echo "- mode: $MODE"
echo "- batch: $BATCH_ID"
echo "- dry-run: $DRY_RUN"

python3 scripts/fill_programmatic_content_and_images.py "${FILL_ARGS[@]}"
python3 scripts/validate_programmatic_readiness.py --source "$SOURCE" --sheet "$SHEET"

echo "[ColorfulMe] Fill + validation complete"
echo "[ColorfulMe] Review generated reports and mark approved rows (content_status=image_status=approved, status=review), then publish using:"
echo "python3 scripts/publish_programmatic_batch.py --source \"$SOURCE\" --sheet \"$SHEET\" --batch-id \"$BATCH_ID\""
