from __future__ import annotations

from datetime import timedelta
from typing import Optional

from flask import current_app

from extensions import db
from models import CreditLedger, CreditWallet, Plan, Subscription, User, current_period_end_for_plan
from colorfulme.utils.security import utcnow


DEFAULT_PLAN_DEFS = [
    {
        'code': 'free',
        'name': 'Free',
        'interval': 'free',
        'monthly_credits': 20,
        'price_cents': 0,
        'api_rpm': 20,
        'stripe_env': None,
    },
    {
        'code': 'starter',
        'name': 'Starter',
        'interval': 'month',
        'monthly_credits': 300,
        'price_cents': 900,
        'api_rpm': 60,
        'stripe_env': 'STRIPE_PRICE_STARTER',
    },
    {
        'code': 'pro',
        'name': 'Pro',
        'interval': 'month',
        'monthly_credits': 1200,
        'price_cents': 2900,
        'api_rpm': 120,
        'stripe_env': 'STRIPE_PRICE_PRO',
    },
    {
        'code': 'studio',
        'name': 'Studio',
        'interval': 'month',
        'monthly_credits': 5000,
        'price_cents': 7900,
        'api_rpm': 300,
        'stripe_env': 'STRIPE_PRICE_STUDIO',
    },
    {
        'code': 'lifetime',
        'name': 'Lifetime',
        'interval': 'lifetime',
        'monthly_credits': 10000,
        'price_cents': 19900,
        'api_rpm': 600,
        'stripe_env': 'STRIPE_PRICE_LIFETIME',
    },
]


class InsufficientCreditsError(Exception):
    pass


def seed_default_plans() -> None:
    for plan_def in DEFAULT_PLAN_DEFS:
        plan = Plan.query.filter_by(code=plan_def['code']).first()
        stripe_price_id = None
        if plan_def['stripe_env']:
            stripe_price_id = current_app.config.get(plan_def['stripe_env']) or None
            stripe_price_id = stripe_price_id or None
        if not plan:
            plan = Plan(code=plan_def['code'])
            db.session.add(plan)

        plan.name = plan_def['name']
        plan.interval = plan_def['interval']
        plan.monthly_credits = plan_def['monthly_credits']
        plan.price_cents = plan_def['price_cents']
        plan.api_rpm = plan_def['api_rpm']
        plan.stripe_price_id = stripe_price_id
        plan.is_active = True

    db.session.commit()


def get_plan(code: str) -> Optional[Plan]:
    return Plan.query.filter_by(code=code, is_active=True).first()


def get_active_subscription(user: User) -> Optional[Subscription]:
    return user.get_active_subscription()


def get_active_plan(user: User) -> Plan:
    active_sub = get_active_subscription(user)
    if active_sub and active_sub.plan:
        return active_sub.plan
    free_plan = get_plan('free')
    if free_plan:
        return free_plan
    # Safety fallback if seed has not run yet.
    seed_default_plans()
    return get_plan('free')


def ensure_wallet_for_user(user: User) -> CreditWallet:
    wallet = user.wallet
    if wallet is None:
        plan = get_active_plan(user)
        wallet = CreditWallet(
            user_id=user.id,
            balance=max(0, plan.monthly_credits),
            cycle_reset_at=utcnow() + timedelta(days=30),
            lifetime_credits_granted=max(0, plan.monthly_credits),
            lifetime_credits_used=0,
        )
        db.session.add(wallet)
        db.session.add(
            CreditLedger(
                user_id=user.id,
                wallet=wallet,
                amount=max(0, plan.monthly_credits),
                reason='initial_grant',
                reference_type='plan',
                reference_id=plan.code,
            )
        )
        db.session.commit()
    return wallet


def ensure_free_subscription(user: User) -> Subscription:
    active = get_active_subscription(user)
    if active:
        return active

    free_plan = get_plan('free')
    if free_plan is None:
        seed_default_plans()
        free_plan = get_plan('free')

    subscription = Subscription(
        user_id=user.id,
        plan_id=free_plan.id,
        status='active',
        current_period_end=current_period_end_for_plan('free'),
    )
    db.session.add(subscription)
    db.session.commit()
    return subscription


def _refresh_cycle_if_needed(user: User, wallet: CreditWallet) -> None:
    now = utcnow()
    if wallet.cycle_reset_at and wallet.cycle_reset_at > now:
        return

    plan = get_active_plan(user)
    refill_amount = max(0, plan.monthly_credits)
    wallet.balance += refill_amount
    wallet.cycle_reset_at = now + timedelta(days=30)
    wallet.lifetime_credits_granted += refill_amount

    db.session.add(
        CreditLedger(
            user_id=user.id,
            wallet_id=wallet.id,
            amount=refill_amount,
            reason='monthly_refill',
            reference_type='plan',
            reference_id=plan.code,
        )
    )
    db.session.commit()


def get_available_credits(user: User) -> int:
    wallet = ensure_wallet_for_user(user)
    _refresh_cycle_if_needed(user, wallet)
    return wallet.balance


def debit_credits(user: User, amount: int, reason: str, reference_type: str = 'generation_job', reference_id: str | None = None) -> None:
    if amount <= 0:
        return

    wallet = ensure_wallet_for_user(user)
    _refresh_cycle_if_needed(user, wallet)

    if wallet.balance < amount:
        raise InsufficientCreditsError(f'Need {amount} credits but only {wallet.balance} available')

    wallet.balance -= amount
    wallet.lifetime_credits_used += amount

    db.session.add(
        CreditLedger(
            user_id=user.id,
            wallet_id=wallet.id,
            amount=-amount,
            reason=reason,
            reference_type=reference_type,
            reference_id=reference_id,
        )
    )
    db.session.commit()


def credit_credits(user: User, amount: int, reason: str, reference_type: str = 'system', reference_id: str | None = None) -> None:
    if amount <= 0:
        return

    wallet = ensure_wallet_for_user(user)
    wallet.balance += amount
    wallet.lifetime_credits_granted += amount

    db.session.add(
        CreditLedger(
            user_id=user.id,
            wallet_id=wallet.id,
            amount=amount,
            reason=reason,
            reference_type=reference_type,
            reference_id=reference_id,
        )
    )
    db.session.commit()


def apply_plan_subscription(
    *,
    user: User,
    plan_code: str,
    stripe_customer_id: str | None = None,
    stripe_subscription_id: str | None = None,
    status: str = 'active',
    current_period_end=None,
) -> Subscription:
    plan = get_plan(plan_code)
    if plan is None:
        raise ValueError(f'Unknown plan code: {plan_code}')

    # Deactivate currently active subscriptions for deterministic entitlement resolution.
    for sub in Subscription.query.filter_by(user_id=user.id).filter(Subscription.status == 'active').all():
        sub.status = 'inactive'

    subscription = None
    if stripe_subscription_id:
        subscription = Subscription.query.filter_by(stripe_subscription_id=stripe_subscription_id).first()

    if not subscription:
        subscription = Subscription(user_id=user.id)
        db.session.add(subscription)

    subscription.plan_id = plan.id
    subscription.status = status
    subscription.stripe_customer_id = stripe_customer_id
    subscription.stripe_subscription_id = stripe_subscription_id
    subscription.current_period_end = current_period_end or current_period_end_for_plan(plan.code)
    subscription.cancel_at_period_end = False

    db.session.commit()

    # Grant plan credits on activation/renewal.
    if status == 'active':
        credit_credits(
            user,
            max(0, plan.monthly_credits),
            reason='plan_activation_refill',
            reference_type='subscription',
            reference_id=str(subscription.id),
        )

    ensure_wallet_for_user(user)
    return subscription
