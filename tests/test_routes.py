def test_core_routes_render(client):
    assert client.get('/').status_code == 200
    assert client.get('/create').status_code == 200
    assert client.get('/pricing').status_code == 200
    assert client.get('/sitemap.xml').status_code == 200


def test_old_receipt_route_not_available(client):
    response = client.get('/generate-walmart-receipt')
    assert response.status_code == 404


def test_homepage_branding(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b'ColorfulMe' in response.data
