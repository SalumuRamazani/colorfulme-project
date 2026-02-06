"""Programmatic content pipeline for ColorfulMe.

Single spreadsheet source powers:
- SEO pages
- Tool pages
- Library entries
"""
from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Tuple

DEFAULT_SOURCE_PATH = 'content/programmatic_content.csv'
DEFAULT_SHEET_NAME = 'content'
DEFAULT_MANIFEST_PATH = 'static/data/programmatic_content_manifest.json'

ALLOWED_ENTRY_TYPES = {'page', 'tool', 'library'}
ALLOWED_STATUSES = {'draft', 'review', 'published'}
PUBLISHED_STATUSES = {'published'}

REQUIRED_COLUMNS = {
    'entry_type',
    'route_path',
    'title',
}


def _safe_text(value: object) -> str:
    if value is None:
        return ''
    return str(value).strip()


def _normalize_path(raw_path: str) -> str:
    value = _safe_text(raw_path)
    if not value:
        return ''
    if not value.startswith('/'):
        value = '/' + value
    if len(value) > 1 and value.endswith('/'):
        value = value[:-1]
    return value


def _normalize_entry_type(raw: str) -> str:
    return _safe_text(raw).lower()


def _normalize_status(raw: str) -> str:
    status = _safe_text(raw).lower()
    if not status:
        return 'draft'
    return status


def _split_pipe(value: str) -> List[str]:
    cleaned = _safe_text(value)
    if not cleaned:
        return []
    return [part.strip() for part in cleaned.split('|') if part.strip()]


def _split_csv(value: str) -> List[str]:
    cleaned = _safe_text(value)
    if not cleaned:
        return []
    return [part.strip() for part in cleaned.split(',') if part.strip()]


def _split_paragraphs(text: str) -> List[str]:
    cleaned = _safe_text(text)
    if not cleaned:
        return []
    return [part.strip() for part in cleaned.split('\n\n') if part.strip()]


def _parse_faq(raw: str) -> List[Dict[str, str]]:
    cleaned = _safe_text(raw)
    if not cleaned:
        return []

    items = []
    for chunk in cleaned.split('||'):
        part = chunk.strip()
        if not part:
            continue
        if '::' in part:
            question, answer = part.split('::', 1)
        else:
            question, answer = part, ''
        question = question.strip()
        answer = answer.strip()
        if question:
            items.append({'question': question, 'answer': answer})
    return items


def _read_csv_rows(path: str, delimiter: str = ',') -> Tuple[List[Dict[str, str]], List[str]]:
    rows: List[Dict[str, str]] = []
    with open(path, 'r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if not reader.fieldnames:
            return [], ['Spreadsheet has no header row']

        header_set = {_safe_text(name) for name in reader.fieldnames}
        missing = REQUIRED_COLUMNS - header_set
        if missing:
            return [], [f"Missing required columns: {', '.join(sorted(missing))}"]

        for row_number, row in enumerate(reader, start=2):
            row_data = {'_row_number': str(row_number)}
            for key, value in row.items():
                row_data[_safe_text(key)] = _safe_text(value)
            rows.append(row_data)

    return rows, []


def _read_xlsx_rows(path: str, sheet_name: str) -> Tuple[List[Dict[str, str]], List[str]]:
    try:
        from openpyxl import load_workbook
    except ModuleNotFoundError:
        return [], ['XLSX input requires openpyxl. Install with pip install openpyxl']

    workbook = load_workbook(filename=path, read_only=True, data_only=True)
    if sheet_name not in workbook.sheetnames:
        return [], [f"Sheet '{sheet_name}' not found. Available: {', '.join(workbook.sheetnames)}"]

    sheet = workbook[sheet_name]
    iterator = sheet.iter_rows(values_only=True)

    try:
        header_row = next(iterator)
    except StopIteration:
        return [], ['Spreadsheet is empty']

    headers = [_safe_text(value) for value in header_row]
    missing = REQUIRED_COLUMNS - set(headers)
    if missing:
        return [], [f"Missing required columns: {', '.join(sorted(missing))}"]

    rows: List[Dict[str, str]] = []
    for row_number, values in enumerate(iterator, start=2):
        row_data: Dict[str, str] = {'_row_number': str(row_number)}
        for index, header in enumerate(headers):
            if not header:
                continue
            row_data[header] = _safe_text(values[index] if index < len(values) else '')
        rows.append(row_data)

    return rows, []


def read_spreadsheet_rows(source_path: str, sheet_name: str = DEFAULT_SHEET_NAME) -> Tuple[List[Dict[str, str]], List[str]]:
    if not os.path.exists(source_path):
        return [], [f'Source spreadsheet not found: {source_path}']

    ext = os.path.splitext(source_path)[1].lower()
    if ext == '.csv':
        return _read_csv_rows(source_path, delimiter=',')
    if ext == '.tsv':
        return _read_csv_rows(source_path, delimiter='\t')
    if ext == '.xlsx':
        return _read_xlsx_rows(source_path, sheet_name)

    return [], [f'Unsupported spreadsheet extension: {ext}. Use .csv, .tsv, or .xlsx']


def build_entries(rows: List[Dict[str, str]]) -> Tuple[List[Dict[str, object]], List[str]]:
    entries = []
    errors = []
    seen_paths = set()

    for row in rows:
        row_no = row.get('_row_number', '?')
        entry_type = _normalize_entry_type(row.get('entry_type', ''))
        route_path = _normalize_path(row.get('route_path', ''))
        title = _safe_text(row.get('title', ''))
        status = _normalize_status(row.get('status', ''))

        if entry_type not in ALLOWED_ENTRY_TYPES:
            errors.append(f"Row {row_no}: entry_type must be one of {', '.join(sorted(ALLOWED_ENTRY_TYPES))}")
            continue
        if not route_path or route_path == '/':
            errors.append(f'Row {row_no}: route_path must be a non-root URL path')
            continue
        if route_path in seen_paths:
            errors.append(f"Row {row_no}: duplicate route_path '{route_path}'")
            continue
        if not title:
            errors.append(f'Row {row_no}: title is required')
            continue
        if status not in ALLOWED_STATUSES:
            errors.append(f"Row {row_no}: status '{status}' must be one of {', '.join(sorted(ALLOWED_STATUSES))}")
            continue

        seen_paths.add(route_path)

        intro = _safe_text(row.get('intro', ''))
        body = _safe_text(row.get('body', ''))

        entry = {
            'entry_type': entry_type,
            'route_path': route_path,
            'slug': _safe_text(row.get('slug', '')) or route_path.strip('/').replace('/', '-'),
            'title': title,
            'meta_description': _safe_text(row.get('meta_description', '')),
            'h1': _safe_text(row.get('h1', '')) or title,
            'intro': intro,
            'intro_paragraphs': _split_paragraphs(intro),
            'body': body,
            'body_paragraphs': _split_paragraphs(body),
            'primary_cta_label': _safe_text(row.get('primary_cta_label', '')),
            'primary_cta_url': _safe_text(row.get('primary_cta_url', '')),
            'secondary_cta_label': _safe_text(row.get('secondary_cta_label', '')),
            'secondary_cta_url': _safe_text(row.get('secondary_cta_url', '')),
            'generation_seed_prompt': _safe_text(row.get('generation_seed_prompt', '')),
            'image_url': _safe_text(row.get('image_url', '')),
            'feature_bullets': _split_pipe(row.get('feature_bullets', '')),
            'faq': _parse_faq(row.get('faq_pairs', '')),
            'tags': _split_csv(row.get('tags', '')),
            'status': status,
            'updated_at': _safe_text(row.get('updated_at', '')),
        }
        entries.append(entry)

    return entries, errors


def build_manifest(entries: List[Dict[str, object]], source_path: str) -> Dict[str, object]:
    page_count = sum(1 for item in entries if item.get('entry_type') == 'page')
    tool_count = sum(1 for item in entries if item.get('entry_type') == 'tool')
    library_count = sum(1 for item in entries if item.get('entry_type') == 'library')

    return {
        'version': 2,
        'source_path': source_path,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'counts': {
            'total': len(entries),
            'pages': page_count,
            'tools': tool_count,
            'library': library_count,
        },
        'entries': entries,
    }


def generate_manifest_from_spreadsheet(source_path: str, output_path: str, sheet_name: str = DEFAULT_SHEET_NAME):
    rows, read_errors = read_spreadsheet_rows(source_path, sheet_name=sheet_name)
    if read_errors:
        return {}, read_errors

    entries, validation_errors = build_entries(rows)
    if validation_errors:
        return {}, validation_errors

    manifest = build_manifest(entries, source_path=source_path)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as handle:
        json.dump(manifest, handle, indent=2)

    return manifest, []


def load_manifest(manifest_path: str) -> Dict[str, object]:
    if not os.path.exists(manifest_path):
        return {
            'version': 2,
            'source_path': '',
            'generated_at': '',
            'counts': {'total': 0, 'pages': 0, 'tools': 0, 'library': 0},
            'entries': [],
        }

    with open(manifest_path, 'r', encoding='utf-8') as handle:
        manifest = json.load(handle)

    entries = manifest.get('entries')
    if not isinstance(entries, list):
        manifest['entries'] = []

    counts = manifest.get('counts')
    if not isinstance(counts, dict):
        manifest['counts'] = {'total': 0, 'pages': 0, 'tools': 0, 'library': 0}

    return manifest


def build_published_route_index(manifest: Dict[str, object]) -> Dict[str, Dict[str, object]]:
    route_index: Dict[str, Dict[str, object]] = {}
    for entry in manifest.get('entries', []):
        if not isinstance(entry, dict):
            continue

        status = _normalize_status(entry.get('status', ''))
        if status not in PUBLISHED_STATUSES:
            continue

        route_path = _normalize_path(entry.get('route_path', ''))
        if not route_path or route_path == '/':
            continue

        route_index[route_path] = entry

    return route_index
