import json

from programmatic_content import build_entries, build_published_route_index, generate_manifest_from_spreadsheet


def test_programmatic_published_filtering(tmp_path):
    rows = [
        {
            '_row_number': '2',
            'entry_type': 'page',
            'route_path': '/a',
            'title': 'A',
            'status': 'published',
        },
        {
            '_row_number': '3',
            'entry_type': 'tool',
            'route_path': '/b',
            'title': 'B',
            'status': 'review',
        },
    ]
    entries, errors = build_entries(rows)
    assert errors == []

    manifest = {'entries': entries}
    index = build_published_route_index(manifest)
    assert '/a' in index
    assert '/b' not in index


def test_programmatic_duplicate_route_validation(tmp_path):
    rows = [
        {'_row_number': '2', 'entry_type': 'page', 'route_path': '/dup', 'title': 'One', 'status': 'published'},
        {'_row_number': '3', 'entry_type': 'tool', 'route_path': '/dup', 'title': 'Two', 'status': 'published'},
    ]
    entries, errors = build_entries(rows)
    assert len(entries) == 1
    assert any('duplicate route_path' in err for err in errors)


def test_generate_manifest_from_csv(tmp_path):
    source = tmp_path / 'content.csv'
    output = tmp_path / 'manifest.json'

    source.write_text(
        'entry_type,route_path,title,status\n'
        'page,/hello,Hello,published\n',
        encoding='utf-8',
    )

    manifest, errors = generate_manifest_from_spreadsheet(str(source), str(output), sheet_name='content')
    assert errors == []
    assert manifest['counts']['total'] == 1

    saved = json.loads(output.read_text(encoding='utf-8'))
    assert saved['entries'][0]['route_path'] == '/hello'
