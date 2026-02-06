import json
from pathlib import Path

import pytest

from colorfulme.app_factory import create_app
from extensions import db
from colorfulme.services.credits_service import seed_default_plans


@pytest.fixture()
def app(tmp_path, monkeypatch):
    manifest_path = tmp_path / 'manifest.json'
    manifest_path.write_text(
        json.dumps(
            {
                'version': 2,
                'source_path': 'tests',
                'generated_at': '2026-02-06T00:00:00Z',
                'counts': {'total': 0, 'pages': 0, 'tools': 0, 'library': 0},
                'entries': [],
            }
        ),
        encoding='utf-8',
    )

    db_path = tmp_path / 'test.db'

    monkeypatch.setenv('TESTING', 'true')
    monkeypatch.setenv('DEBUG', 'false')
    monkeypatch.setenv('ALLOW_FAKE_AI', 'true')
    monkeypatch.setenv('STRICT_MODERATION', 'true')
    monkeypatch.setenv('SESSION_SECRET', 'test-secret')
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{db_path}')
    monkeypatch.setenv('PROGRAMMATIC_CONTENT_MANIFEST', str(manifest_path))
    monkeypatch.setenv('OPENAI_API_KEY', '')
    monkeypatch.setenv('STRIPE_SECRET_KEY', '')
    monkeypatch.setenv('STRIPE_WEBHOOK_SECRET', '')

    app = create_app()
    app.config.update(TESTING=True)

    with app.app_context():
        db.drop_all()
        db.create_all()
        seed_default_plans()

    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def login_user(client):
    def _login(email='test@example.com'):
        send = client.post('/auth/email/send-code', json={'email': email})
        assert send.status_code == 200
        code = send.get_json()['code']

        verify = client.post('/auth/email/verify-code', json={'email': email, 'code': code})
        assert verify.status_code == 200
        return verify.get_json()['user']

    return _login
