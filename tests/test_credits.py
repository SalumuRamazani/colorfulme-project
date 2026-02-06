import pytest

from colorfulme.services.credits_service import InsufficientCreditsError, debit_credits, ensure_wallet_for_user
from models import User


def test_credit_balance_and_debit(app, login_user):
    user_data = login_user('credits@example.com')

    with app.app_context():
        user = User.query.filter_by(email=user_data['email']).first()
        wallet = ensure_wallet_for_user(user)
        before = wallet.balance
        debit_credits(user, 1, reason='test_debit')
        assert wallet.balance == before - 1


def test_insufficient_credits_raises(app, login_user):
    user_data = login_user('low@example.com')

    with app.app_context():
        user = User.query.filter_by(email=user_data['email']).first()
        with pytest.raises(InsufficientCreditsError):
            debit_credits(user, 99999, reason='too_much')
