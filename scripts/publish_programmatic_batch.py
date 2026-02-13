#!/usr/bin/env python3
"""Publish approved programmatic rows in a controlled batch."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from colorfulme.services.programmatic_pipeline_io import ensure_headers, load_rows_with_headers, save_rows  # noqa: E402
from programmatic_content import DEFAULT_MANIFEST_PATH, generate_manifest_from_spreadsheet  # noqa: E402


def _safe_text(value: object) -> str:
    if value is None:
        return ''
    return str(value).strip()


def _report_path(base_dir: str, batch_id: str) -> Path:
    target = Path(base_dir)
    target.mkdir(parents=True, exist_ok=True)
    return target / f'publish_report_{batch_id}.json'


def _should_publish(row: Dict[str, str], *, batch_id: str) -> bool:
    status = _safe_text(row.get('status')).lower()
    content_status = _safe_text(row.get('content_status')).lower()
    image_status = _safe_text(row.get('image_status')).lower()

    if status != 'review':
        return False
    if content_status != 'approved':
        return False
    if image_status != 'approved':
        return False

    if batch_id:
        row_batch = _safe_text(row.get('generation_batch_id'))
        if row_batch != batch_id:
            return False

    return True


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Publish approved programmatic rows from review to published')
    parser.add_argument('--source', default=os.environ.get('PROGRAMMATIC_CONTENT_SOURCE', 'content/programmatic_content.csv'))
    parser.add_argument('--sheet', default=os.environ.get('PROGRAMMATIC_CONTENT_SHEET', 'content'))
    parser.add_argument('--batch-id', default='')
    parser.add_argument('--max-publish', type=int, default=0)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--manifest-output', default=os.environ.get('PROGRAMMATIC_CONTENT_MANIFEST', DEFAULT_MANIFEST_PATH))
    parser.add_argument('--report-dir', default='static/data/pipeline_reports')
    args = parser.parse_args(argv)

    rows, headers, errors = load_rows_with_headers(args.source, args.sheet)
    if errors:
        print('Failed to read source spreadsheet:', file=sys.stderr)
        for item in errors:
            print(f'- {item}', file=sys.stderr)
        return 1

    headers = ensure_headers(headers)

    now = datetime.now(timezone.utc).isoformat()
    promoted = 0
    scanned = 0
    promoted_routes: List[str] = []

    for row in rows:
        scanned += 1
        if args.max_publish and promoted >= args.max_publish:
            continue

        if not _should_publish(row, batch_id=args.batch_id):
            continue

        promoted += 1
        promoted_routes.append(_safe_text(row.get('route_path')))

        if args.dry_run:
            continue

        row['status'] = 'published'
        row['last_reviewed_at'] = now
        row['updated_at'] = now

    manifest_errors: List[str] = []
    if promoted and not args.dry_run:
        save_rows(args.source, args.sheet, rows, headers)

    manifest_counts = {}
    if not args.dry_run:
        manifest, manifest_errors = generate_manifest_from_spreadsheet(args.source, args.manifest_output, args.sheet)
        if not manifest_errors:
            manifest_counts = manifest.get('counts', {})

    report = {
        'generated_at': now,
        'source': args.source,
        'sheet': args.sheet,
        'batch_id': args.batch_id,
        'dry_run': bool(args.dry_run),
        'max_publish': args.max_publish,
        'counts': {
            'rows_scanned': scanned,
            'rows_promoted': promoted,
        },
        'promoted_routes': promoted_routes,
        'manifest_output': args.manifest_output,
        'manifest_errors': manifest_errors,
        'manifest_counts': manifest_counts,
    }

    batch_label = args.batch_id or datetime.now(timezone.utc).strftime('batch-%Y%m%d%H%M%S')
    report_file = _report_path(args.report_dir, batch_label)
    report_file.write_text(json.dumps(report, indent=2), encoding='utf-8')
    latest = Path(args.report_dir) / 'publish_report_latest.json'
    latest.write_text(json.dumps(report, indent=2), encoding='utf-8')

    print('Programmatic publish complete')
    print(f'- scanned: {scanned}')
    print(f'- promoted: {promoted}')
    print(f'- dry-run: {args.dry_run}')
    print(f'- report: {report_file}')
    if manifest_errors:
        print('- manifest: failed')
        for item in manifest_errors:
            print(f'  - {item}')
        return 1

    if not args.dry_run:
        print(f'- manifest: {args.manifest_output}')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
