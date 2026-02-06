from __future__ import annotations

from datetime import datetime
import logging

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
import stripe

from extensions import db
from models import Plan, Subscription, User
from colorfulme.services.credits_service import apply_plan_subscription, credit_credits, get_plan


billing_bp = Blueprint('billing', __name__)


@billing_bp.get('/pricing')
def pricing():
    plans = Plan.query.filter(Plan.code.in_(['free', 'starter', 'pro', 'studio', 'lifetime'])).order_by(Plan.price_cents.asc()).all()
    return render_template('pricing.html', plans=plans)


@billing_bp.post('/create-checkout-session')
def create_checkout_session():
    if not current_user.is_authenticated:
        return redirect(url_for('web.index'))

    plan_code = request.form.get('plan_code') or (request.get_json(silent=True) or {}).get('plan_code')
    plan_code = (plan_code or '').strip().lower()

    plan = get_plan(plan_code)
    if not plan or plan.code == 'free':
        return jsonify({'error': 'Invalid paid plan'}), 400

    stripe_key = current_app.config.get('STRIPE_SECRET_KEY', '').strip()
    if not stripe_key:
        return jsonify({'error': 'Stripe is not configured. Set STRIPE_SECRET_KEY.'}), 503

    stripe.api_key = stripe_key

    success_url = f"{request.url_root.rstrip('/')}{url_for('billing.billing_success')}?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{request.url_root.rstrip('/')}{url_for('billing.pricing')}"

    metadata = {
        'user_id': current_user.id,
        'plan_code': plan.code,
    }

    mode = 'subscription'
    if plan.interval == 'lifetime':
        mode = 'payment'

    if plan.stripe_price_id:
        line_item = {'price': plan.stripe_price_id, 'quantity': 1}
    else:
        price_data = {
            'currency': 'usd',
            'unit_amount': max(1, plan.price_cents),
            'product_data': {
                'name': f'ColorfulMe {plan.name}',
                'description': f'{plan.name} plan for ColorfulMe',
            },
        }
        if mode == 'subscription':
            price_data['recurring'] = {'interval': 'month'}
        line_item = {'price_data': price_data, 'quantity': 1}

    try:
        checkout_session = stripe.checkout.Session.create(
            customer_email=current_user.email,
            mode=mode,
            line_items=[line_item],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata,
        )
    except Exception as exc:
        logging.exception('Stripe checkout session creation failed')
        return jsonify({'error': str(exc)}), 500

    return redirect(checkout_session.url, code=303)


@billing_bp.get('/billing/success')
@login_required
def billing_success():
    session_id = request.args.get('session_id')
    if not session_id:
        return redirect(url_for('web.dashboard'))

    stripe_key = current_app.config.get('STRIPE_SECRET_KEY', '').strip()
    if not stripe_key:
        return redirect(url_for('web.dashboard'))

    stripe.api_key = stripe_key

    try:
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        _apply_checkout_session(checkout_session)
    except Exception as exc:
        logging.warning('Could not process billing success session: %s', exc)

    return redirect(url_for('web.dashboard'))


@billing_bp.post('/stripe-webhook')
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature', '')

    stripe_key = current_app.config.get('STRIPE_SECRET_KEY', '').strip()
    webhook_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET', '').strip()

    if stripe_key:
        stripe.api_key = stripe_key

    event = None
    try:
        if webhook_secret:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        else:
            event = request.get_json(force=True)
    except Exception as exc:
        return jsonify({'error': f'Invalid webhook payload: {exc}'}), 400

    event_type = event.get('type')
    data = (event.get('data') or {}).get('object') or {}

    try:
        if event_type == 'checkout.session.completed':
            _apply_checkout_session(data)
        elif event_type == 'invoice.paid':
            _apply_invoice_paid(data)
        elif event_type == 'customer.subscription.deleted':
            _mark_subscription_status(data.get('id'), 'canceled')
        elif event_type == 'invoice.payment_failed':
            _mark_subscription_status(data.get('subscription'), 'past_due')
    except Exception as exc:
        logging.exception('Stripe webhook processing failed')
        return jsonify({'error': str(exc)}), 500

    return jsonify({'received': True})


def _apply_checkout_session(checkout_session):
    metadata = checkout_session.get('metadata') or {}
    user_id = metadata.get('user_id')
    plan_code = metadata.get('plan_code')

    if not user_id or not plan_code:
        return

    user = db.session.get(User, user_id)
    if not user:
        return

    payment_status = checkout_session.get('payment_status')
    mode = checkout_session.get('mode')
    if mode != 'subscription' and payment_status not in {'paid', 'no_payment_required'}:
        return

    stripe_subscription_id = checkout_session.get('subscription')
    stripe_customer_id = checkout_session.get('customer')

    apply_plan_subscription(
        user=user,
        plan_code=plan_code,
        stripe_customer_id=stripe_customer_id,
        stripe_subscription_id=stripe_subscription_id,
        status='active',
    )


def _apply_invoice_paid(invoice):
    stripe_subscription_id = invoice.get('subscription')
    if not stripe_subscription_id:
        return

    subscription = Subscription.query.filter_by(stripe_subscription_id=stripe_subscription_id).first()
    if not subscription:
        return

    subscription.status = 'active'

    period_end = invoice.get('period_end') or invoice.get('current_period_end')
    if period_end:
        subscription.current_period_end = datetime.utcfromtimestamp(int(period_end))

    db.session.commit()

    if subscription.plan:
        credit_credits(
            subscription.user,
            max(0, subscription.plan.monthly_credits),
            reason='invoice_paid_refill',
            reference_type='subscription',
            reference_id=str(subscription.id),
        )


def _mark_subscription_status(stripe_subscription_id: str | None, status: str):
    if not stripe_subscription_id:
        return

    subscription = Subscription.query.filter_by(stripe_subscription_id=stripe_subscription_id).first()
    if not subscription:
        return

    subscription.status = status
    db.session.commit()
