#!/usr/bin/env python3
"""Fill programmatic copy + hero drawings at scale (idempotent)."""
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

from colorfulme.app_factory import create_app  # noqa: E402
from colorfulme.services.programmatic_fill_service import ProgrammaticFillService  # noqa: E402
from colorfulme.services.programmatic_image_service import ProgrammaticImageService  # noqa: E402
from colorfulme.services.programmatic_pipeline_io import (  # noqa: E402
    apply_entry_to_row,
    ensure_headers,
    load_rows_with_headers,
    normalize_entry_from_row,
    save_rows,
)


def _safe_text(value: object) -> str:
    if value is None:
        return ''
    return str(value).strip()


def _parse_filters(raw_filters: List[str]) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for item in raw_filters:
        if '=' not in item:
            continue
        key, value = item.split('=', 1)
        key = _safe_text(key).lower()
        value = _safe_text(value).lower()
        if key and value:
            result[key] = value
    return result


def _matches_filters(entry: Dict[str, object], filters: Dict[str, str]) -> bool:
    if not filters:
        return True
    for key, expected in filters.items():
        current = _safe_text(entry.get(key)).lower()
        if current != expected:
            return False
    return True


def _default_batch_id() -> str:
    return datetime.now(timezone.utc).strftime('batch-%Y%m%d%H%M%S')


def _report_path(base_dir: str, batch_id: str) -> Path:
    target = Path(base_dir)
    target.mkdir(parents=True, exist_ok=True)
    return target / f'fill_report_{batch_id}.json'


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Fill programmatic content and images for live-ready publishing')
    parser.add_argument('--source', default=os.environ.get('PROGRAMMATIC_CONTENT_SOURCE', 'content/programmatic_content.csv'))
    parser.add_argument('--sheet', default=os.environ.get('PROGRAMMATIC_CONTENT_SHEET', 'content'))
    parser.add_argument('--mode', choices=['content', 'images', 'all'], default='all')
    parser.add_argument('--filter', action='append', default=[], help='Filter rows by key=value, e.g. entry_type=tool')
    parser.add_argument('--batch-id', default='')
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--force-content', action='store_true')
    parser.add_argument('--force-images', action='store_true')
    parser.add_argument('--report-dir', default='static/data/pipeline_reports')
    args = parser.parse_args(argv)

    batch_id = args.batch_id or _default_batch_id()
    rows, headers, errors = load_rows_with_headers(args.source, args.sheet)
    if errors:
        print('Failed to read source spreadsheet:', file=sys.stderr)
        for item in errors:
            print(f'- {item}', file=sys.stderr)
        return 1

    headers = ensure_headers(headers)
    filters = _parse_filters(args.filter)

    fill_service = ProgrammaticFillService()

    processed = 0
    changed = 0
    content_changed = 0
    image_changed = 0
    failed = 0
    skipped = 0
    row_reports = []

    app = create_app()
    with app.app_context():
        image_service = ProgrammaticImageService()

        for row in rows:
            normalized, row_errors = normalize_entry_from_row(row)
            if row_errors or not normalized:
                failed += 1
                row_reports.append(
                    {
                        'row': row.get('_row_number', '?'),
                        'route_path': row.get('route_path', ''),
                        'status': 'failed',
                        'errors': row_errors,
                    }
                )
                continue

            if not _matches_filters(normalized, filters):
                skipped += 1
                row_reports.append(
                    {
                        'row': row.get('_row_number', '?'),
                        'route_path': normalized.get('route_path', ''),
                        'status': 'skipped',
                        'reason': 'filtered_out',
                    }
                )
                continue

            if args.limit and processed >= args.limit:
                skipped += 1
                row_reports.append(
                    {
                        'row': row.get('_row_number', '?'),
                        'route_path': normalized.get('route_path', ''),
                        'status': 'skipped',
                        'reason': 'limit_reached',
                    }
                )
                continue

            processed += 1
            working = dict(normalized)
            actions = []
            step_errors = []

            if args.mode in {'content', 'all'}:
                working, content_actions = fill_service.fill_entry(
                    working,
                    force=args.force_content,
                    batch_id=batch_id,
                )
                if content_actions:
                    content_changed += 1
                    actions.append({'content': content_actions})

            if args.mode in {'images', 'all'}:
                working, image_report = image_service.process_entry(
                    working,
                    force=args.force_images,
                    dry_run=args.dry_run,
                    batch_id=batch_id,
                )
                actions.append({'image': image_report})
                if image_report.get('status') in {'generated', 'would_generate'}:
                    image_changed += 1
                if image_report.get('status') == 'failed':
                    failed += 1
                    step_errors.append(image_report.get('reason', 'image generation failed'))

            # Keep review gate for non-live entries.
            current_status = _safe_text(working.get('status')).lower() or 'draft'
            if current_status != 'published' and actions:
                working['status'] = 'review'

            row_after = apply_entry_to_row(row, working)
            row_was_changed = any(_safe_text(row.get(h)) != _safe_text(row_after.get(h)) for h in headers)

            if row_was_changed:
                changed += 1
                if not args.dry_run:
                    row.update(row_after)

            row_reports.append(
                {
                    'row': row.get('_row_number', '?'),
                    'route_path': working.get('route_path', ''),
                    'status': 'ok' if not step_errors else 'failed',
                    'changed': row_was_changed,
                    'actions': actions,
                    'errors': step_errors,
                }
            )

    if changed and not args.dry_run:
        save_rows(args.source, args.sheet, rows, headers)

    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'batch_id': batch_id,
        'source': args.source,
        'sheet': args.sheet,
        'mode': args.mode,
        'filters': filters,
        'dry_run': bool(args.dry_run),
        'force_content': bool(args.force_content),
        'force_images': bool(args.force_images),
        'counts': {
            'rows_total': len(rows),
            'rows_processed': processed,
            'rows_changed': changed,
            'content_changed': content_changed,
            'image_changed': image_changed,
            'rows_failed': failed,
            'rows_skipped': skipped,
        },
        'rows': row_reports,
    }

    report_file = _report_path(args.report_dir, batch_id)
    report_file.write_text(json.dumps(report, indent=2), encoding='utf-8')

    latest = Path(args.report_dir) / 'fill_report_latest.json'
    latest.write_text(json.dumps(report, indent=2), encoding='utf-8')

    print('Programmatic fill complete')
    print(f'- source: {args.source}')
    print(f'- mode: {args.mode}')
    print(f'- batch: {batch_id}')
    print(f'- processed: {processed}')
    print(f'- changed: {changed}')
    print(f'- failed: {failed}')
    print(f'- report: {report_file}')

    return 0 if failed == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
