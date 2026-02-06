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


def test_generator_routes_render(client):
    assert client.get('/ai-coloring-page-generator').status_code == 200
    assert client.get('/generators/name-coloring-page-generator').status_code == 200
    assert client.get('/prompt-generators/midjourney-prompt-generator').status_code == 200
