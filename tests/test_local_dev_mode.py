import json

from colorfulme.app_factory import create_app
from colorfulme.services.credits_service import seed_default_plans
from extensions import db


def _create_local_dev_app(tmp_path, monkeypatch):
    manifest_path = tmp_path / 'manifest.json'
    manifest_path.write_text(
        json.dumps(
            {
                'version': 2,
                'source_path': 'tests',
                'generated_at': '2026-02-07T00:00:00Z',
                'counts': {'total': 0, 'pages': 0, 'tools': 0, 'library': 0},
                'entries': [],
            }
        ),
        encoding='utf-8',
    )

    db_path = tmp_path / 'local-dev.db'

    monkeypatch.setenv('TESTING', 'true')
    monkeypatch.setenv('DEBUG', 'true')
    monkeypatch.setenv('ALLOW_FAKE_AI', 'true')
    monkeypatch.setenv('STRICT_MODERATION', 'true')
    monkeypatch.setenv('SESSION_SECRET', 'test-secret')
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{db_path}')
    monkeypatch.setenv('PROGRAMMATIC_CONTENT_MANIFEST', str(manifest_path))
    monkeypatch.setenv('OPENAI_API_KEY', '')
    monkeypatch.setenv('STRIPE_SECRET_KEY', '')
    monkeypatch.setenv('STRIPE_WEBHOOK_SECRET', '')
    monkeypatch.setenv('LOCAL_DEV_AUTO_LOGIN', 'true')
    monkeypatch.setenv('LOCAL_DEV_AUTO_LOGIN_EMAIL', 'local-dev@colorfulme.app')
    monkeypatch.setenv('LOCAL_DEV_AUTO_LOGIN_NAME', 'Local Dev')
    monkeypatch.setenv('LOCAL_DEV_UNLIMITED_CREDITS', 'true')

    app = create_app()
    app.config.update(TESTING=True)

    with app.app_context():
        db.drop_all()
        db.create_all()
        seed_default_plans()

    return app


def test_local_auto_login_me_endpoint(tmp_path, monkeypatch):
    app = _create_local_dev_app(tmp_path, monkeypatch)
    client = app.test_client()

    response = client.get('/api/v1/me')
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['authenticated'] is True
    assert payload['user']['email'] == 'local-dev@colorfulme.app'


def test_local_auto_login_generation_without_manual_auth(tmp_path, monkeypatch):
    app = _create_local_dev_app(tmp_path, monkeypatch)
    client = app.test_client()

    response = client.post(
        '/api/v1/generations/text',
        json={
            'prompt': 'A happy turtle in a garden',
            'style': 'clean line art',
            'aspect_ratio': '1:1',
            'difficulty': 'easy',
        },
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['job']['asset']['png_url']
    assert payload['job']['asset']['pdf_url']


def test_local_unlimited_credits_no_exhaustion(tmp_path, monkeypatch):
    app = _create_local_dev_app(tmp_path, monkeypatch)
    client = app.test_client()

    for _ in range(25):
        response = client.post(
            '/api/v1/generations/text',
            json={
                'prompt': 'A friendly dinosaur near trees',
                'style': 'clean line art',
                'aspect_ratio': '1:1',
                'difficulty': 'easy',
            },
        )
        assert response.status_code == 200


def test_local_login_required_routes_work(tmp_path, monkeypatch):
    app = _create_local_dev_app(tmp_path, monkeypatch)
    client = app.test_client()

    response = client.get('/dashboard')
    assert response.status_code == 200


def test_bearer_token_still_validated_with_auto_login(tmp_path, monkeypatch):
    app = _create_local_dev_app(tmp_path, monkeypatch)
    client = app.test_client()

    response = client.get('/api/v1/me/credits', headers={'Authorization': 'Bearer invalid-token'})
    assert response.status_code == 401
    assert response.get_json()['error'] == 'Invalid API key'
