from datetime import datetime
from extensions import db
# Flask-Dance removed - not needed for boilerplate
# from flask_dance.consumer.storage.sqla import OAuthConsumerMixin
from flask_login import UserMixin
from sqlalchemy import UniqueConstraint
import uuid
import hashlib
import secrets


# (IMPORTANT) This table is mandatory for Replit Auth, don't drop it.
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String, primary_key=True)
    email = db.Column(db.String, unique=True, nullable=True)
    first_name = db.Column(db.String, nullable=True)
    last_name = db.Column(db.String, nullable=True)
    profile_image_url = db.Column(db.String, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime,
                           default=datetime.now,
                           onupdate=datetime.now)
    
    # Welcome offer tracking (24-hour limited offer for new users)
    welcome_offer_expires_at = db.Column(db.DateTime, nullable=True)
    welcome_offer_popup_seen = db.Column(db.Boolean, default=False)
    
    # Relationship to subscriptions
    subscriptions = db.relationship('Subscription', back_populates='user', lazy=True)
    
    # Relationship to webhooks
    webhooks = db.relationship('WebhookIntegration', back_populates='user', lazy=True, cascade='all, delete-orphan')
    
    # Relationship to incoming webhook config
    incoming_webhook_config = db.relationship('IncomingWebhookConfig', back_populates='user', uselist=False, lazy=True, cascade='all, delete-orphan')
    
    # Relationship to saved templates
    saved_templates = db.relationship('SavedTemplate', back_populates='user', lazy=True, cascade='all, delete-orphan')
    
    # Relationship to receipt logs
    receipt_logs = db.relationship('ReceiptLog', back_populates='user', lazy=True, cascade='all, delete-orphan')
    
    def has_active_subscription(self):
        """Check if user has an active subscription that hasn't expired"""
        from datetime import datetime
        import logging
        
        # Log the check
        logging.info(f"Checking subscription for user {self.id} ({self.email})")
        
        # Get all subscriptions for debugging
        all_subs = Subscription.query.filter_by(user_id=self.id).all()
        logging.info(f"Found {len(all_subs)} total subscriptions for user {self.id}")
        for sub in all_subs:
            logging.info(f"  Sub ID {sub.id}: status={sub.status}, expires_at={sub.expires_at}, is_expired={sub.expires_at < datetime.now() if sub.expires_at else 'N/A'}")
        
        active_sub = Subscription.query.filter_by(
            user_id=self.id,
            status='active'
        ).filter(
            (Subscription.expires_at == None) | (Subscription.expires_at > datetime.now())
        ).first()
        
        has_sub = active_sub is not None
        logging.info(f"User {self.id} has_active_subscription result: {has_sub}, active_sub: {active_sub}")
        return has_sub
    
    def is_welcome_offer_valid(self):
        """Check if the 24-hour welcome offer is still valid"""
        from datetime import datetime
        
        # No offer if already has subscription (covers any paid plan)
        if self.has_active_subscription():
            return False
        
        # No offer if expires_at not set
        if not self.welcome_offer_expires_at:
            return False
        
        # Check if offer hasn't expired
        return datetime.now() < self.welcome_offer_expires_at
    
    def get_welcome_offer_seconds_remaining(self):
        """Get seconds remaining for welcome offer, or 0 if expired"""
        from datetime import datetime
        
        if not self.welcome_offer_expires_at:
            return 0
        
        remaining = (self.welcome_offer_expires_at - datetime.now()).total_seconds()
        return max(0, int(remaining))
    
    def set_welcome_offer(self, hours=24):
        """Set the welcome offer expiry time (default 24 hours from now)"""
        from datetime import datetime, timedelta
        self.welcome_offer_expires_at = datetime.now() + timedelta(hours=hours)
    
    def get_active_weekly_subscription(self):
        """Get the active weekly subscription if exists"""
        from datetime import datetime
        return Subscription.query.filter_by(
            user_id=self.id,
            plan_type='weekly',
            status='active'
        ).filter(
            (Subscription.expires_at == None) | (Subscription.expires_at > datetime.now())
        ).first()
    
    def is_eligible_for_weekly_to_lifetime_upgrade(self):
        """Check if user is eligible for the $20.50 upgrade offer:
        1. Has an active weekly subscription
        2. Account created less than 24 hours ago
        """
        from datetime import datetime, timedelta
        
        # Check if has active weekly subscription
        weekly_sub = self.get_active_weekly_subscription()
        
        if not weekly_sub:
            return False
        
        # Check if account created less than 24 hours ago
        if not self.created_at:
            return False
        
        account_age = datetime.now() - self.created_at
        
        if account_age > timedelta(hours=24):
            return False
        
        return True
    
    def get_upgrade_offer_seconds_remaining(self):
        """Get seconds remaining for the weekly-to-lifetime upgrade offer (24 hours from account creation)"""
        from datetime import datetime, timedelta
        
        if not self.created_at:
            return 0
        
        # Offer expires 24 hours after account creation
        offer_expires = self.created_at + timedelta(hours=24)
        remaining = (offer_expires - datetime.now()).total_seconds()
        return max(0, int(remaining))


# OAuth model removed - Replit Auth no longer used
# Implement your own authentication system here
# class OAuth(OAuthConsumerMixin, db.Model):
#     user_id = db.Column(db.String, db.ForeignKey(User.id))
#     browser_session_key = db.Column(db.String, nullable=False)
#     user = db.relationship(User)


# Subscription model for tracking user subscriptions
class Subscription(db.Model):
    __tablename__ = 'subscriptions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    stripe_customer_id = db.Column(db.String, nullable=True)
    stripe_subscription_id = db.Column(db.String, unique=True, nullable=True)
    plan_type = db.Column(db.String, nullable=False)  # 'weekly', 'monthly', 'yearly'
    status = db.Column(db.String, default='active')  # 'active', 'canceled', 'expired'
    cancel_at_period_end = db.Column(db.Boolean, default=False)  # Track if user requested cancellation at period end
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    expires_at = db.Column(db.DateTime, nullable=True)
    
    # Relationship back to user
    user = db.relationship('User', back_populates='subscriptions')


# Webhook Integration model for connecting external services
class WebhookIntegration(db.Model):
    __tablename__ = 'webhook_integrations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    
    name = db.Column(db.String, nullable=False)
    endpoint_url = db.Column(db.String, nullable=False)
    access_token = db.Column(db.String, nullable=True)
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    last_triggered = db.Column(db.DateTime, nullable=True)
    
    # Relationship back to user
    user = db.relationship('User', back_populates='webhooks')


# Incoming Webhook Configuration - allows users to receive webhooks FROM external services
class IncomingWebhookConfig(db.Model):
    __tablename__ = 'incoming_webhook_configs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=True, index=True)
    
    public_id = db.Column(db.String, unique=True, nullable=False, index=True)
    api_key_hash = db.Column(db.String, nullable=False)
    api_key_hint = db.Column(db.String, nullable=False)
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    last_used = db.Column(db.DateTime, nullable=True)
    last_rotated_at = db.Column(db.DateTime, nullable=True)
    
    # Relationship back to user
    user = db.relationship('User', back_populates='incoming_webhook_config')
    
    @staticmethod
    def generate_api_key():
        """Generate a secure API key"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def hash_api_key(api_key):
        """Hash an API key using SHA256"""
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    def verify_api_key(self, api_key):
        """Verify if the provided API key matches the stored hash"""
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        return api_key_hash == self.api_key_hash


# Incoming Webhook Events - track all webhook deliveries and their status
class IncomingWebhookEvent(db.Model):
    __tablename__ = 'incoming_webhook_events'
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.String, unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    
    config_id = db.Column(db.Integer, db.ForeignKey('incoming_webhook_configs.id'), nullable=False)
    
    status = db.Column(db.String, nullable=False)  # 'pending', 'success', 'failed', 'invalid_auth'
    payload = db.Column(db.JSON, nullable=True)
    headers = db.Column(db.JSON, nullable=True)
    
    ip_address = db.Column(db.String, nullable=True)
    user_agent = db.Column(db.String, nullable=True)
    
    error_message = db.Column(db.Text, nullable=True)
    http_status = db.Column(db.Integer, nullable=True)
    
    received_at = db.Column(db.DateTime, default=datetime.now)
    processed_at = db.Column(db.DateTime, nullable=True)


# Blog Post model for storing auto-published content from Outrank
class BlogPost(db.Model):
    __tablename__ = 'blog_posts'
    id = db.Column(db.Integer, primary_key=True)
    
    # Outrank integration
    outrank_id = db.Column(db.String, nullable=True, unique=True, index=True)
    
    # Article content
    title = db.Column(db.String, nullable=False)
    slug = db.Column(db.String, unique=True, nullable=False, index=True)
    content_markdown = db.Column(db.Text, nullable=True)
    content_html = db.Column(db.Text, nullable=True)
    meta_description = db.Column(db.String, nullable=True)
    image_url = db.Column(db.String, nullable=True)
    
    # Tags stored as JSON array
    tags = db.Column(db.JSON, nullable=True)
    
    # Publishing info
    published = db.Column(db.Boolean, default=True, index=True)
    published_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)


# Blog Article model for storing auto-published content from Outrank (legacy)
class BlogArticle(db.Model):
    __tablename__ = 'blog_articles'
    id = db.Column(db.Integer, primary_key=True)
    
    # Article content
    title = db.Column(db.String, nullable=False)
    slug = db.Column(db.String, unique=True, nullable=False)
    content_markdown = db.Column(db.Text, nullable=True)
    content_html = db.Column(db.Text, nullable=True)
    meta_description = db.Column(db.String, nullable=True)
    image_url = db.Column(db.String, nullable=True)
    
    # Tags stored as JSON array
    tags = db.Column(db.JSON, nullable=True)
    
    # Publishing info
    published = db.Column(db.Boolean, default=True)
    published_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)


# Saved Template model - stores user-created custom receipt templates
class SavedTemplate(db.Model):
    __tablename__ = 'saved_templates'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Template metadata
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=True)
    template_type = db.Column(db.String, nullable=False, default='custom')  # 'walmart', 'target', 'starbucks', 'custom'
    
    # Template configuration stored as JSON
    config_json = db.Column(db.JSON, nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    last_used_at = db.Column(db.DateTime, nullable=True)
    
    # Relationship back to user
    user = db.relationship('User', back_populates='saved_templates')
    
    # Unique constraint on user_id + name
    __table_args__ = (
        UniqueConstraint('user_id', 'name', name='uq_user_template_name'),
    )


# Receipt Generation Log - for admin monitoring and fraud detection
class ReceiptLog(db.Model):
    __tablename__ = 'receipt_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=True, index=True)
    
    # Receipt details
    template_type = db.Column(db.String, nullable=False)  # 'walmart', 'target', etc.
    store_name = db.Column(db.String, nullable=True)
    ip_address = db.Column(db.String, nullable=True)
    user_agent = db.Column(db.String, nullable=True)
    
    # Receipt content hash for duplicate detection
    content_hash = db.Column(db.String, nullable=True, index=True)
    
    # Flags for suspicious activity
    is_suspicious = db.Column(db.Boolean, default=False)
    suspicion_reason = db.Column(db.String, nullable=True)  # 'high_volume', 'duplicate', 'fraud_pattern', etc.
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.now, index=True)
    
    # Relationship back to user
    user = db.relationship('User', back_populates='receipt_logs')
