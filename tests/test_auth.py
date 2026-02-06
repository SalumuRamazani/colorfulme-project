def test_email_otp_login_and_logout(client):
    send = client.post('/auth/email/send-code', json={'email': 'auth@example.com'})
    assert send.status_code == 200
    payload = send.get_json()
    assert payload['success'] is True
    assert 'code' in payload

    verify = client.post(
        '/auth/email/verify-code',
        json={'email': 'auth@example.com', 'code': payload['code']},
    )
    assert verify.status_code == 200

    me = client.get('/api/v1/me')
    assert me.status_code == 200
    assert me.get_json()['authenticated'] is True

    logout = client.post('/auth/logout')
    assert logout.status_code == 200
    assert logout.get_json()['success'] is True


def test_google_dev_callback_login(client):
    response = client.get('/auth/google/callback?code=dev-demo&email=google@example.com', follow_redirects=True)
    assert response.status_code == 200

    me = client.get('/api/v1/me')
    assert me.status_code == 200
    data = me.get_json()
    assert data['authenticated'] is True
    assert data['user']['email'] == 'google@example.com'
