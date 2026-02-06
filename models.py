from __future__ import annotations

from datetime import datetime, timedelta
import uuid

from flask_login import UserMixin
from sqlalchemy import UniqueConstraint

from extensions import db


def _utcnow():
    return datetime.utcnow()


def _uuid_str() -> str:
    return str(uuid.uuid4())


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.String(36), primary_key=True, default=_uuid_str)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(120), nullable=True)
    locale = db.Column(db.String(20), nullable=False, default='en-US')

    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)
    last_login_at = db.Column(db.DateTime, nullable=True)

    auth_identities = db.relationship('AuthIdentity', back_populates='user', cascade='all, delete-orphan')
    subscriptions = db.relationship('Subscription', back_populates='user', cascade='all, delete-orphan')
    wallet = db.relationship('CreditWallet', back_populates='user', uselist=False, cascade='all, delete-orphan')
    credit_ledger_entries = db.relationship('CreditLedger', back_populates='user', cascade='all, delete-orphan')
    generation_jobs = db.relationship('GenerationJob', back_populates='user', cascade='all, delete-orphan')
    generated_assets = db.relationship('GeneratedAsset', back_populates='user', cascade='all, delete-orphan')
    api_keys = db.relationship('ApiKey', back_populates='user', cascade='all, delete-orphan')
    api_usage_events = db.relationship('ApiUsageEvent', back_populates='user', cascade='all, delete-orphan')

    def get_id(self):
        return self.id

    def get_active_subscription(self) -> 'Subscription | None':
        now = _utcnow()
        return (
            Subscription.query.filter_by(user_id=self.id)
            .filter(Subscription.status == 'active')
            .filter((Subscription.current_period_end.is_(None)) | (Subscription.current_period_end > now))
            .order_by(Subscription.created_at.desc())
            .first()
        )

    def get_plan_code(self) -> str:
        subscription = self.get_active_subscription()
        if subscription and subscription.plan:
            return subscription.plan.code
        return 'free'


class AuthIdentity(db.Model):
    __tablename__ = 'auth_identities'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    provider = db.Column(db.String(20), nullable=False, index=True)  # google, email
    provider_user_id = db.Column(db.String(255), nullable=False, index=True)
    email = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)

    user = db.relationship('User', back_populates='auth_identities')

    __table_args__ = (
        UniqueConstraint('provider', 'provider_user_id', name='uq_provider_user_id'),
    )


class EmailOtpCode(db.Model):
    __tablename__ = 'email_otp_codes'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    code_hash = db.Column(db.String(128), nullable=False)
    purpose = db.Column(db.String(40), nullable=False, default='login')
    expires_at = db.Column(db.DateTime, nullable=False)
    consumed_at = db.Column(db.DateTime, nullable=True)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    ip_address = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)


class Plan(db.Model):
    __tablename__ = 'plans'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    interval = db.Column(db.String(20), nullable=False)  # free, month, lifetime
    monthly_credits = db.Column(db.Integer, nullable=False, default=0)
    price_cents = db.Column(db.Integer, nullable=False, default=0)
    stripe_price_id = db.Column(db.String(255), nullable=True)
    api_rpm = db.Column(db.Integer, nullable=False, default=20)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)

    subscriptions = db.relationship('Subscription', back_populates='plan')


class Subscription(db.Model):
    __tablename__ = 'subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('plans.id'), nullable=False)

    stripe_customer_id = db.Column(db.String(255), nullable=True)
    stripe_subscription_id = db.Column(db.String(255), nullable=True, unique=True, index=True)
    status = db.Column(db.String(40), nullable=False, default='active')
    current_period_end = db.Column(db.DateTime, nullable=True)
    cancel_at_period_end = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    user = db.relationship('User', back_populates='subscriptions')
    plan = db.relationship('Plan', back_populates='subscriptions')


class CreditWallet(db.Model):
    __tablename__ = 'credit_wallets'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), unique=True, nullable=False, index=True)
    balance = db.Column(db.Integer, nullable=False, default=0)
    cycle_reset_at = db.Column(db.DateTime, nullable=True)
    lifetime_credits_granted = db.Column(db.Integer, nullable=False, default=0)
    lifetime_credits_used = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    user = db.relationship('User', back_populates='wallet')
    ledger_entries = db.relationship('CreditLedger', back_populates='wallet', cascade='all, delete-orphan')


class CreditLedger(db.Model):
    __tablename__ = 'credit_ledger'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    wallet_id = db.Column(db.Integer, db.ForeignKey('credit_wallets.id'), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(120), nullable=False)
    reference_type = db.Column(db.String(40), nullable=True)
    reference_id = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)

    user = db.relationship('User', back_populates='credit_ledger_entries')
    wallet = db.relationship('CreditWallet', back_populates='ledger_entries')


class GenerationJob(db.Model):
    __tablename__ = 'generation_jobs'

    id = db.Column(db.String(36), primary_key=True, default=_uuid_str)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)

    mode = db.Column(db.String(20), nullable=False)  # text, photo, recolor
    prompt = db.Column(db.Text, nullable=True)
    style = db.Column(db.String(80), nullable=True)
    aspect_ratio = db.Column(db.String(20), nullable=True)
    difficulty = db.Column(db.String(40), nullable=True)

    status = db.Column(db.String(20), nullable=False, default='queued')  # queued, processing, completed, failed, blocked
    cost_credits = db.Column(db.Integer, nullable=False, default=0)
    error_message = db.Column(db.Text, nullable=True)

    source_asset_id = db.Column(db.String(36), nullable=True)

    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', back_populates='generation_jobs')
    assets = db.relationship('GeneratedAsset', back_populates='job', cascade='all, delete-orphan', foreign_keys='GeneratedAsset.job_id')


class GeneratedAsset(db.Model):
    __tablename__ = 'generated_assets'

    id = db.Column(db.String(36), primary_key=True, default=_uuid_str)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    job_id = db.Column(db.String(36), db.ForeignKey('generation_jobs.id'), nullable=False, index=True)

    png_key = db.Column(db.String(512), nullable=False)
    pdf_key = db.Column(db.String(512), nullable=False)
    png_url = db.Column(db.String(1024), nullable=True)
    pdf_url = db.Column(db.String(1024), nullable=True)

    width = db.Column(db.Integer, nullable=True)
    height = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)

    user = db.relationship('User', back_populates='generated_assets')
    job = db.relationship('GenerationJob', back_populates='assets', foreign_keys=[job_id])


class PromptPreset(db.Model):
    __tablename__ = 'prompt_presets'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    style = db.Column(db.String(80), nullable=True)
    is_featured = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)


class ProgrammaticEntry(db.Model):
    __tablename__ = 'programmatic_entries'

    id = db.Column(db.Integer, primary_key=True)
    route_path = db.Column(db.String(255), unique=True, nullable=False, index=True)
    entry_type = db.Column(db.String(20), nullable=False)  # page, tool, library
    title = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='draft')
    manifest_version = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)


class ApiKey(db.Model):
    __tablename__ = 'api_keys'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)

    name = db.Column(db.String(80), nullable=False)
    key_prefix = db.Column(db.String(20), nullable=False, index=True)
    key_hash = db.Column(db.String(128), nullable=False, unique=True, index=True)

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    plan_rpm_override = db.Column(db.Integer, nullable=True)
    last_used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)
    revoked_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', back_populates='api_keys')
    usage_events = db.relationship('ApiUsageEvent', back_populates='api_key', cascade='all, delete-orphan')


class ApiUsageEvent(db.Model):
    __tablename__ = 'api_usage_events'

    id = db.Column(db.Integer, primary_key=True)
    api_key_id = db.Column(db.Integer, db.ForeignKey('api_keys.id'), nullable=True, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True, index=True)

    endpoint = db.Column(db.String(255), nullable=False)
    method = db.Column(db.String(10), nullable=False)
    status_code = db.Column(db.Integer, nullable=False)
    credits_used = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False, index=True)

    api_key = db.relationship('ApiKey', back_populates='usage_events')
    user = db.relationship('User', back_populates='api_usage_events')


def current_period_end_for_plan(plan_code: str) -> datetime:
    now = _utcnow()
    if plan_code == 'lifetime':
        return now + timedelta(days=365 * 30)
    return now + timedelta(days=30)
