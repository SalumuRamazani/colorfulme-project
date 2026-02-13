import json

from colorfulme.services import programmatic_service


def _seed_generator_manifest(app):
    payload = {
        'version': 2,
        'source_path': 'tests',
        'generated_at': '2026-02-13T00:00:00Z',
        'counts': {'total': 4, 'pages': 1, 'tools': 3, 'library': 0},
        'entries': [
            {
                'entry_type': 'page',
                'route_path': '/free-coloring-pages/for-toddlers',
                'title': 'Free Coloring Pages For Toddlers',
                'h1': 'Free Coloring Pages For Toddlers',
                'intro': 'Create simple printable pages for toddlers with clear outlines and family-safe prompts.',
                'body': (
                    'This category helps you generate simple toddler-friendly pages with bold outlines and clear spaces. '
                    'Use one friendly subject and keep scenes uncluttered for easier coloring.\n\n'
                    'For better results, describe one main action and avoid tiny decorative details. '
                    'Short prompts usually produce cleaner printable outputs.\n\n'
                    'Download PNG or PDF and print test pages before creating a full set for activities.'
                ),
                'feature_bullets': ['Simple prompts', 'Printable formats', 'Family-safe output'],
                'faq': [
                    {'question': 'Is this safe for toddlers?', 'answer': 'Yes, prompts are family-safe and moderated.'},
                    {'question': 'Can I print at home?', 'answer': 'Yes, PNG and PDF are available for easy printing.'},
                ],
                'status': 'published',
            },
            {
                'entry_type': 'tool',
                'route_path': '/ai-coloring-page-generator',
                'title': 'AI Coloring Page Generator',
                'intro': 'Create printable coloring pages from text prompts in seconds.',
                'body': (
                    'Use this generator to create family-safe coloring pages with clean outlines and simple scenes.\n\n'
                    'Start with one main subject, then add style details like bold lines and open areas.\n\n'
                    'Download PNG or PDF after generation for printing and sharing.'
                ),
                'faq': [
                    {'question': 'Can I use this for classrooms?', 'answer': 'Yes, it is designed for printable activities.'},
                    {'question': 'Is output family-safe?', 'answer': 'Yes, moderation is enabled.'},
                ],
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

    assert client.get('/free-coloring-pages/for-toddlers').status_code == 200
    assert client.get('/ai-coloring-page-generator').status_code == 200
    assert client.get('/generators/name-coloring-page-generator').status_code == 200
    assert client.get('/prompt-generators/midjourney-prompt-generator').status_code == 200


def test_readability_sections_render(client, app):
    with app.app_context():
        _seed_generator_manifest(app)

    category = client.get('/free-coloring-pages/for-toddlers')
    assert category.status_code == 200
    assert b'Overview' in category.data
    assert b'How To Use This Category' in category.data
    assert b'Practical Tips' in category.data
    assert b'Frequently Asked Questions' in category.data

    tool = client.get('/ai-coloring-page-generator')
    assert tool.status_code == 200
    assert b'How To Use This Page' in tool.data
    assert b'FAQ' in tool.data
