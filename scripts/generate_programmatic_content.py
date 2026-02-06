#!/usr/bin/env python3
"""Generate ColorfulMe programmatic manifest from one spreadsheet."""
import argparse
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from programmatic_content import (  # noqa: E402
    DEFAULT_MANIFEST_PATH,
    DEFAULT_SHEET_NAME,
    DEFAULT_SOURCE_PATH,
    generate_manifest_from_spreadsheet,
)


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate pages, tools, and library entries from one spreadsheet')
    parser.add_argument(
        '--source',
        default=os.environ.get('PROGRAMMATIC_CONTENT_SOURCE', DEFAULT_SOURCE_PATH),
        help='Path to source spreadsheet (.csv/.tsv/.xlsx)',
    )
    parser.add_argument(
        '--sheet',
        default=os.environ.get('PROGRAMMATIC_CONTENT_SHEET', DEFAULT_SHEET_NAME),
        help='Sheet name for .xlsx sources',
    )
    parser.add_argument(
        '--output',
        default=os.environ.get('PROGRAMMATIC_CONTENT_MANIFEST', DEFAULT_MANIFEST_PATH),
        help='Output manifest JSON path',
    )
    args = parser.parse_args()

    manifest, errors = generate_manifest_from_spreadsheet(
        source_path=args.source,
        output_path=args.output,
        sheet_name=args.sheet,
    )

    if errors:
        print('Programmatic manifest generation failed:', file=sys.stderr)
        for error in errors:
            print(f'- {error}', file=sys.stderr)
        return 1

    counts = manifest.get('counts', {})
    print('Programmatic manifest generated')
    print(f"- source: {args.source}")
    print(f"- output: {args.output}")
    print(f"- total: {counts.get('total', 0)}")
    print(f"- pages: {counts.get('pages', 0)}")
    print(f"- tools: {counts.get('tools', 0)}")
    print(f"- library: {counts.get('library', 0)}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
