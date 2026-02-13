import json

from colorfulme.services import programmatic_service


def _seed_generator_manifest(app):
    payload = {
        'version': 2,
        'source_path': 'tests',
        'generated_at': '2026-02-13T00:00:00Z',
        'counts': {'total': 2, 'pages': 0, 'tools': 2, 'library': 0},
        'entries': [
            {
                'entry_type': 'tool',
                'route_path': '/ai-coloring-page-generator',
                'title': 'AI Coloring Page Generator',
                'status': 'published',
            },
            {
                'entry_type': 'tool',
                'route_path': '/generators/name-coloring-page-generator',
                'title': 'Name Coloring Page Generator',
                'status': 'published',
            },
            {
                'entry_type': 'tool',
                'route_path': '/prompt-generators/midjourney-prompt-generator',
                'title': 'Midjourney Prompt Generator',
                'status': 'published',
            },
        ],
    }

    manifest_path = app.config['PROGRAMMATIC_CONTENT_MANIFEST']
    with open(manifest_path, 'w', encoding='utf-8') as handle:
        json.dump(payload, handle)

    programmatic_service._cache.update({'path': None, 'mtime': None, 'manifest': None, 'index': None})


def test_core_routes_render(client):
    assert client.get('/').status_code == 200
    assert client.get('/create').status_code == 200
    assert client.get('/generators').status_code == 200
    assert client.get('/prompt-generators').status_code == 200
    assert client.get('/pricing').status_code == 200
    assert client.get('/sitemap.xml').status_code == 200


def test_old_receipt_route_not_available(client):
    response = client.get('/generate-walmart-receipt')
    assert response.status_code == 404


def test_homepage_branding(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b'ColorfulMe' in response.data


def test_generator_routes_render(client, app):
    with app.app_context():
        _seed_generator_manifest(app)

    assert client.get('/ai-coloring-page-generator').status_code == 200
    assert client.get('/generators/name-coloring-page-generator').status_code == 200
    assert client.get('/prompt-generators/midjourney-prompt-generator').status_code == 200
