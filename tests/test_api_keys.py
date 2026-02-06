def test_api_key_lifecycle(client, login_user):
    login_user('keys@example.com')

    create = client.post('/api/v1/developer/keys', json={'name': 'Test Key'})
    assert create.status_code == 200
    payload = create.get_json()
    key_value = payload['api_key']
    key_id = payload['key_id']

    list_resp = client.get('/api/v1/developer/keys')
    assert list_resp.status_code == 200
    assert len(list_resp.get_json()['keys']) >= 1

    credits = client.get('/api/v1/me/credits', headers={'Authorization': f'Bearer {key_value}'})
    assert credits.status_code == 200

    revoke = client.delete(f'/api/v1/developer/keys/{key_id}')
    assert revoke.status_code == 200

    # Clear session auth so request depends on bearer token only.
    client.post('/auth/logout')
    blocked = client.get('/api/v1/me/credits', headers={'Authorization': f'Bearer {key_value}'})
    assert blocked.status_code == 401
