"""
Configuration module for ReceiptForge
Environment-based configuration for Flask application
"""
import os


class Config:
    """Base configuration class with environment variables"""

    # Secret Keys
    SECRET_KEY = os.environ.get('SESSION_SECRET') or 'dev-secret-key-CHANGE-IN-PRODUCTION'

    # Database Configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///receiptforge.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    # Stripe Configuration
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

    # Feature Flags
    ENABLE_SUBSCRIPTIONS = os.environ.get('ENABLE_SUBSCRIPTIONS', 'true').lower() == 'true'
    REQUIRE_AUTH_FOR_FREE = os.environ.get('REQUIRE_AUTH_FOR_FREE', 'false').lower() == 'true'

    # Application Settings
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

    # PDF Generation Settings
    PDF_FONT = os.environ.get('PDF_FONT', 'Courier')
    PDF_FONT_SIZE = int(os.environ.get('PDF_FONT_SIZE', '10'))


class DevelopmentConfig(Config):
    """Development environment configuration"""
    DEBUG = True
    LOG_LEVEL = 'DEBUG'


class ProductionConfig(Config):
    """Production environment configuration"""
    DEBUG = False
    # Force HTTPS in production
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'


class TestingConfig(Config):
    """Testing environment configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(config_name=None):
    """Get configuration object based on environment"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    return config.get(config_name, DevelopmentConfig)
