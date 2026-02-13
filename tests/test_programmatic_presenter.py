from colorfulme.services.programmatic_presenter import build_entry_view_model


def test_presenter_splits_dense_body_into_sections():
    entry = {
        'entry_type': 'page',
        'route_path': '/free-coloring-pages/for-toddlers',
        'title': 'Free Coloring Pages For Toddlers',
        'intro': 'Create toddler-friendly printable pages quickly.',
        'body': (
            'Free Coloring Pages For Toddlers helps families create simple printable pages with clear outlines. '
            'Use one subject and short prompts so each result stays easy to color and easy to print. '
            'If details look busy, simplify the request and regenerate with fewer objects.\n\n'
            'This category works well for home activities, classroom stations, and rainy day projects. '
            'Keep instructions family-safe and age-appropriate for younger children and early learners. '
            'Download PNG or PDF for easy sharing and print packs.\n\n'
            'For consistency, keep a reusable prompt pattern and only swap theme details each time. '
            'That approach saves time and keeps style quality steady across larger sets of pages.'
        ),
        'faq': [{'question': 'Can I print these?', 'answer': 'Yes.'}],
        'feature_bullets': ['Family-safe', 'PNG + PDF', 'Printable line art'],
    }
    vm = build_entry_view_model(entry, page_kind='category')

    assert vm['hero_title'] == 'Free Coloring Pages For Toddlers'
    assert len(vm['content_sections']) == 3
    assert vm['content_sections'][0]['id'] == 'overview'
    assert vm['content_sections'][1]['id'] == 'how_to_use'
    assert vm['content_sections'][2]['id'] == 'practical_tips'
    assert vm['content_sections'][0]['paragraphs']
    assert vm['content_sections'][1]['paragraphs']
    assert vm['content_sections'][2]['paragraphs']


def test_presenter_has_safe_fallbacks_for_sparse_entry():
    entry = {
        'entry_type': 'tool',
        'route_path': '/ai-coloring-page-generator',
        'title': 'AI Coloring Page Generator',
    }
    vm = build_entry_view_model(entry, page_kind='programmatic')

    assert vm['hero_intro']
    assert len(vm['quick_facts']) == 4
    assert vm['primary_cta_url'] == '/create'
    assert vm['secondary_cta_url'] == '/free-coloring-pages'
    assert len(vm['how_to_steps']) == 4
    assert len(vm['practical_tips']) >= 3


def test_presenter_normalizes_related_links_and_faq():
    entry = {
        'entry_type': 'page',
        'route_path': '/free-coloring-pages/for-kids',
        'title': 'Free Coloring Pages For Kids',
        'faq': [
            {'question': 'How fast is generation?', 'answer': 'Usually seconds.'},
            {'question': '', 'answer': 'Missing question should be removed.'},
        ],
    }
    related = [
        {'title': 'Free Coloring Pages For Toddlers', 'route_path': '/free-coloring-pages/for-toddlers'},
        {'title': '', 'route_path': '/free-coloring-pages/invalid'},
    ]
    vm = build_entry_view_model(entry, page_kind='category', related_categories=related)

    assert len(vm['faq_items']) == 1
    assert vm['faq_items'][0]['question'] == 'How fast is generation?'
    assert len(vm['related_links']) == 1
    assert vm['related_links'][0]['route_path'] == '/free-coloring-pages/for-toddlers'
