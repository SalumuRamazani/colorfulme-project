from models import User
from colorfulme.services.credits_service import get_active_plan


def test_checkout_webhook_applies_plan(client, app, login_user):
    user = login_user('billing@example.com')

    payload = {
        'type': 'checkout.session.completed',
        'data': {
            'object': {
                'metadata': {'user_id': user['id'], 'plan_code': 'starter'},
                'payment_status': 'paid',
                'mode': 'payment',
                'customer': 'cus_test',
                'subscription': None,
            }
        },
    }

    response = client.post('/stripe-webhook', json=payload)
    assert response.status_code == 200

    with app.app_context():
        db_user = User.query.filter_by(id=user['id']).first()
        assert get_active_plan(db_user).code == 'starter'
