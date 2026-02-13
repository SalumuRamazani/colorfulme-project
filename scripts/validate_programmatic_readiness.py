#!/usr/bin/env python3
"""Validate readiness of programmatic pages for publishing."""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from colorfulme.app_factory import create_app  # noqa: E402
from colorfulme.services.programmatic_pipeline_io import load_rows_with_headers, normalize_entry_from_row  # noqa: E402


def _safe_text(value: object) -> str:
    if value is None:
        return ''
    return str(value).strip()


def _word_count(text: str) -> int:
    return len([item for item in text.replace('\n', ' ').split(' ') if item.strip()])


def _severity_for_row(status: str, base: str = 'error') -> str:
    if status == 'published':
        return base
    if base == 'error':
        return 'warning'
    return base


def _requires_detail_blocks(entry_type: str, route_path: str) -> bool:
    if entry_type == 'tool':
        return True
    return entry_type == 'page' and not route_path.startswith('/blog/')


def _resolve_local_file(app_static_folder: str, image_url: str) -> Path | None:
    clean = image_url.split('?', 1)[0].split('#', 1)[0]
    if not clean.startswith('/static/'):
        return None
    relative = clean[len('/static/'):]
    return Path(app_static_folder) / relative


def _add_issue(issues: List[Dict[str, object]], *, row: str, route_path: str, field: str, severity: str, message: str) -> None:
    issues.append(
        {
            'row': row,
            'route_path': route_path,
            'field': field,
            'severity': severity,
            'message': message,
        }
    )


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Validate programmatic content readiness for go-live')
    parser.add_argument('--source', default=os.environ.get('PROGRAMMATIC_CONTENT_SOURCE', 'content/programmatic_content.csv'))
    parser.add_argument('--sheet', default=os.environ.get('PROGRAMMATIC_CONTENT_SHEET', 'content'))
    parser.add_argument('--report-dir', default='static/data/pipeline_reports')
    args = parser.parse_args(argv)

    rows, _headers, errors = load_rows_with_headers(args.source, args.sheet)
    if errors:
        print('Failed to read source spreadsheet:', file=sys.stderr)
        for item in errors:
            print(f'- {item}', file=sys.stderr)
        return 1

    issues: List[Dict[str, object]] = []
    by_route = Counter()

    app = create_app()
    with app.app_context():
        static_folder = app.static_folder

        for row in rows:
            route_path = _safe_text(row.get('route_path'))
            if route_path:
                by_route[route_path] += 1

            normalized, row_errors = normalize_entry_from_row(row)
            if row_errors or not normalized:
                _add_issue(
                    issues,
                    row=row.get('_row_number', '?'),
                    route_path=route_path,
                    field='row',
                    severity='error',
                    message='; '.join(row_errors or ['Invalid row']),
                )
                continue

            status = _safe_text(normalized.get('status')).lower() or 'draft'
            row_no = _safe_text(row.get('_row_number', '?'))
            route_path = _safe_text(normalized.get('route_path'))
            entry_type = _safe_text(normalized.get('entry_type')).lower()

            meta = _safe_text(normalized.get('meta_description'))
            if len(meta) < 120 or len(meta) > 160:
                _add_issue(
                    issues,
                    row=row_no,
                    route_path=route_path,
                    field='meta_description',
                    severity=_severity_for_row(status),
                    message=f'meta_description length should be 120-160 (got {len(meta)})',
                )

            intro = _safe_text(normalized.get('intro'))
            intro_words = _word_count(intro)
            if intro_words < 30 or intro_words > 60 or '\n\n' in intro:
                _add_issue(
                    issues,
                    row=row_no,
                    route_path=route_path,
                    field='intro',
                    severity=_severity_for_row(status),
                    message=f'intro should be single paragraph with 30-60 words (got {intro_words})',
                )

            body = _safe_text(normalized.get('body'))
            paragraphs = [part for part in body.split('\n\n') if part.strip()]
            body_words = _word_count(body)
            if body_words < 220 or len(paragraphs) < 3:
                _add_issue(
                    issues,
                    row=row_no,
                    route_path=route_path,
                    field='body',
                    severity=_severity_for_row(status),
                    message=f'body should have >=220 words and >=3 paragraphs (got {body_words} words, {len(paragraphs)} paragraphs)',
                )

            if body_words < 180:
                _add_issue(
                    issues,
                    row=row_no,
                    route_path=route_path,
                    field='body',
                    severity='warning',
                    message=f'thin content detected (<180 words): {body_words}',
                )

            max_paragraph_words = 120
            for paragraph_index, paragraph in enumerate(paragraphs, start=1):
                paragraph_words = _word_count(paragraph)
                if paragraph_words > max_paragraph_words:
                    _add_issue(
                        issues,
                        row=row_no,
                        route_path=route_path,
                        field='body',
                        severity='warning',
                        message=(
                            f'paragraph {paragraph_index} is dense ({paragraph_words} words); '
                            f'aim for <= {max_paragraph_words} words'
                        ),
                    )

            if _requires_detail_blocks(entry_type, route_path):
                bullets = list(normalized.get('feature_bullets') or [])
                faq = list(normalized.get('faq') or [])
                if len(bullets) < 3:
                    _add_issue(
                        issues,
                        row=row_no,
                        route_path=route_path,
                        field='feature_bullets',
                        severity=_severity_for_row(status),
                        message=f'expected at least 3 feature bullets (got {len(bullets)})',
                    )
                if len(faq) < 2:
                    _add_issue(
                        issues,
                        row=row_no,
                        route_path=route_path,
                        field='faq_pairs',
                        severity=_severity_for_row(status),
                        message=f'expected at least 2 FAQ items (got {len(faq)})',
                    )

            image_url = _safe_text(normalized.get('image_url'))
            if not image_url:
                _add_issue(
                    issues,
                    row=row_no,
                    route_path=route_path,
                    field='image_url',
                    severity=_severity_for_row(status),
                    message='missing image_url',
                )
            else:
                if image_url == '/static/images/colorfulme/hero-samples.svg':
                    _add_issue(
                        issues,
                        row=row_no,
                        route_path=route_path,
                        field='image_url',
                        severity=_severity_for_row(status),
                        message='uses deprecated hero-samples.svg placeholder',
                    )

                local_file = _resolve_local_file(static_folder, image_url)
                if local_file is not None and not local_file.exists():
                    _add_issue(
                        issues,
                        row=row_no,
                        route_path=route_path,
                        field='image_url',
                        severity=_severity_for_row(status),
                        message=f'local image not found: {local_file}',
                    )

            if not _safe_text(normalized.get('generation_seed_prompt')):
                _add_issue(
                    issues,
                    row=row_no,
                    route_path=route_path,
                    field='generation_seed_prompt',
                    severity='warning',
                    message='missing generation_seed_prompt',
                )

            image_status = _safe_text(normalized.get('image_status')).lower()
            if image_status == 'failed':
                _add_issue(
                    issues,
                    row=row_no,
                    route_path=route_path,
                    field='image_status',
                    severity=_severity_for_row(status),
                    message='image_status is failed',
                )

    for route_path, count in by_route.items():
        if count > 1:
            _add_issue(
                issues,
                row='-',
                route_path=route_path,
                field='route_path',
                severity='error',
                message=f'duplicate route_path appears {count} times',
            )

    errors_count = sum(1 for issue in issues if issue['severity'] == 'error')
    warnings_count = sum(1 for issue in issues if issue['severity'] == 'warning')

    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'source': args.source,
        'sheet': args.sheet,
        'counts': {
            'rows_total': len(rows),
            'issues_total': len(issues),
            'errors': errors_count,
            'warnings': warnings_count,
        },
        'issues': issues,
    }

    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')

    json_path = report_dir / f'readiness_report_{timestamp}.json'
    csv_path = report_dir / f'readiness_report_{timestamp}.csv'

    json_path.write_text(json.dumps(report, indent=2), encoding='utf-8')

    with csv_path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['row', 'route_path', 'field', 'severity', 'message'])
        writer.writeheader()
        for issue in issues:
            writer.writerow(issue)

    latest_json = report_dir / 'readiness_report_latest.json'
    latest_csv = report_dir / 'readiness_report_latest.csv'
    latest_json.write_text(json.dumps(report, indent=2), encoding='utf-8')
    with latest_csv.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['row', 'route_path', 'field', 'severity', 'message'])
        writer.writeheader()
        for issue in issues:
            writer.writerow(issue)

    flat_json = Path('static/data/readiness_report.json')
    flat_csv = Path('static/data/readiness_report.csv')
    flat_json.parent.mkdir(parents=True, exist_ok=True)
    flat_json.write_text(json.dumps(report, indent=2), encoding='utf-8')
    with flat_csv.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['row', 'route_path', 'field', 'severity', 'message'])
        writer.writeheader()
        for issue in issues:
            writer.writerow(issue)

    print('Programmatic readiness validation complete')
    print(f'- rows: {len(rows)}')
    print(f'- issues: {len(issues)}')
    print(f'- errors: {errors_count}')
    print(f'- warnings: {warnings_count}')
    print(f'- json report: {json_path}')
    print(f'- csv report: {csv_path}')

    return 0 if errors_count == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
