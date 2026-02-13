from __future__ import annotations

from pathlib import Path

from programmatic_content import build_entries
from colorfulme.services.programmatic_fill_service import ProgrammaticFillService
from colorfulme.services.programmatic_image_service import ProgrammaticImageService


def _word_count(text: str) -> int:
    return len([item for item in (text or '').replace('\n', ' ').split(' ') if item.strip()])


def test_optional_pipeline_columns_preserved_in_manifest_entries():
    rows = [
        {
            '_row_number': '2',
            'entry_type': 'tool',
            'route_path': '/generators/sample-tool',
            'title': 'Sample Tool',
            'status': 'review',
            'content_status': 'approved',
            'image_status': 'generated',
            'primary_keyword': 'sample coloring tool',
            'secondary_keywords': 'sample printable|kids activity',
            'content_brief': 'Brief text',
            'image_style': 'clean line art',
            'image_aspect_ratio': '4:5',
            'image_prompt_override': 'draw sample',
            'asset_local_path': 'static/images/programmatic/sample-tool-hero.png',
            'asset_hash': 'abc123',
            'generation_batch_id': 'batch-1',
            'last_generated_at': '2026-02-13T00:00:00+00:00',
            'last_reviewed_at': '2026-02-13T00:00:00+00:00',
            'qa_notes': 'ok',
        }
    ]

    entries, errors = build_entries(rows)
    assert errors == []
    entry = entries[0]
    assert entry['content_status'] == 'approved'
    assert entry['image_status'] == 'generated'
    assert entry['primary_keyword'] == 'sample coloring tool'
    assert entry['secondary_keywords'] == ['sample printable', 'kids activity']
    assert entry['asset_hash'] == 'abc123'
    assert entry['generation_batch_id'] == 'batch-1'


def test_fill_service_is_idempotent_without_force():
    service = ProgrammaticFillService()
    entry = {
        'entry_type': 'tool',
        'route_path': '/generators/new-tool',
        'slug': 'new-tool',
        'title': 'New Tool',
        'meta_description': 'Short',
        'intro': 'Tiny intro',
        'body': 'Too short',
        'feature_bullets': [],
        'faq': [],
        'status': 'draft',
        'content_status': 'pending',
        'image_status': 'pending',
        'generation_seed_prompt': '',
    }

    updated_once, changes_once = service.fill_entry(entry, force=False, batch_id='batch-x')
    assert changes_once
    assert _word_count(updated_once['body']) >= 220
    assert updated_once['generation_seed_prompt']
    assert updated_once['content_status'] == 'generated'

    updated_twice, changes_twice = service.fill_entry(updated_once, force=False, batch_id='batch-x')
    assert changes_twice == []
    assert updated_twice['body'] == updated_once['body']


def test_image_service_generates_and_skips_when_hash_matches(app, tmp_path):
    static_root = tmp_path / 'static'
    static_root.mkdir(parents=True, exist_ok=True)
    app.static_folder = str(static_root)

    entry = {
        'entry_type': 'tool',
        'route_path': '/generators/image-tool',
        'slug': 'image-tool',
        'title': 'Image Tool',
        'primary_keyword': 'image tool coloring page',
        'generation_seed_prompt': 'A happy turtle in a park',
        'image_style': 'clean line art',
        'image_aspect_ratio': '4:5',
        'image_url': '',
        'asset_hash': '',
        'image_status': 'pending',
    }

    with app.app_context():
        service = ProgrammaticImageService()
        generated, report = service.process_entry(entry, batch_id='batch-img', force=False, dry_run=False)
        assert report['status'] == 'generated'
        assert generated['image_url'].startswith('/static/images/programmatic/')

        local_path = Path(app.static_folder) / generated['image_url'][len('/static/'):]
        assert local_path.exists()

        second, second_report = service.process_entry(generated, batch_id='batch-img', force=False, dry_run=False)
        assert second_report['status'] == 'skipped'
        assert second['image_url'] == generated['image_url']
