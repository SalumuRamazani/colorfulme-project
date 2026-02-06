import base64
from io import BytesIO

from PIL import Image


def _sample_image_b64():
    image = Image.new('RGB', (64, 64), 'white')
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode('utf-8')


def test_text_generation_success(client, login_user):
    login_user('gen@example.com')

    response = client.post(
        '/api/v1/generations/text',
        json={
            'prompt': 'A happy whale with bubbles',
            'style': 'clean line art',
            'aspect_ratio': '1:1',
            'difficulty': 'easy',
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'completed'
    assert data['job']['asset']['asset_id']


def test_blocked_prompt_returns_blocked_status(client, login_user):
    login_user('blocked@example.com')

    response = client.post(
        '/api/v1/generations/text',
        json={
            'prompt': 'nude explicit content',
            'style': 'clean line art',
            'aspect_ratio': '1:1',
            'difficulty': 'easy',
        },
    )
    assert response.status_code == 422
    assert response.get_json()['status'] == 'blocked'


def test_photo_generation_success(client, login_user):
    login_user('photo@example.com')

    response = client.post(
        '/api/v1/generations/photo',
        json={
            'prompt': 'Turn this into coloring page',
            'style': 'clean line art',
            'aspect_ratio': '1:1',
            'difficulty': 'standard',
            'source_image_base64': _sample_image_b64(),
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'completed'
