import logging
import os
from datetime import timedelta

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from extensions import db, login_manager


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def create_app() -> Flask:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder=os.path.join(project_root, 'templates'),
        static_folder=os.path.join(project_root, 'static'),
    )

    app.config.update(
        SECRET_KEY=os.getenv('SESSION_SECRET', 'dev-secret-key-change-in-production'),
        SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', 'sqlite:///colorfulme.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={
            'pool_pre_ping': True,
            'pool_recycle': 300,
        },
        DEBUG=_bool_env('DEBUG', False),
        TESTING=_bool_env('TESTING', False),
        HOST=os.getenv('HOST', '0.0.0.0'),
        PORT=int(os.getenv('PORT', '5003')),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        REMEMBER_COOKIE_DURATION=timedelta(days=30),
        PROGRAMMATIC_CONTENT_SOURCE=os.getenv('PROGRAMMATIC_CONTENT_SOURCE', 'content/programmatic_content.csv'),
        PROGRAMMATIC_CONTENT_SHEET=os.getenv('PROGRAMMATIC_CONTENT_SHEET', 'content'),
        PROGRAMMATIC_CONTENT_MANIFEST=os.getenv('PROGRAMMATIC_CONTENT_MANIFEST', 'static/data/programmatic_content_manifest.json'),
        OPENAI_MODEL=os.getenv('OPENAI_MODEL', 'gpt-image-1.5'),
        OPENAI_MODEL_FALLBACK=os.getenv('OPENAI_MODEL_FALLBACK', 'gpt-image-1-mini'),
        OPENAI_MODEL_ECONOMY=os.getenv('OPENAI_MODEL_ECONOMY', 'gpt-image-1.5'),
        OPENAI_MODEL_BALANCED=os.getenv('OPENAI_MODEL_BALANCED', 'gpt-image-1.5'),
        OPENAI_MODEL_PREMIUM=os.getenv('OPENAI_MODEL_PREMIUM', 'gpt-image-1.5'),
        OPENAI_QUALITY_ECONOMY=os.getenv('OPENAI_QUALITY_ECONOMY', 'low'),
        OPENAI_QUALITY_BALANCED=os.getenv('OPENAI_QUALITY_BALANCED', 'medium'),
        OPENAI_QUALITY_PREMIUM=os.getenv('OPENAI_QUALITY_PREMIUM', 'high'),
        OPENAI_IMAGE_QUALITY_DEFAULT=os.getenv('OPENAI_IMAGE_QUALITY_DEFAULT', 'medium'),
        OPENAI_API_KEY=os.getenv('OPENAI_API_KEY', ''),
        ALLOW_FAKE_AI=_bool_env('ALLOW_FAKE_AI', True),
        STRICT_MODERATION=_bool_env('STRICT_MODERATION', True),
        APP_BRAND_NAME=os.getenv('APP_BRAND_NAME', 'ColorfulMe'),
        STRIPE_SECRET_KEY=os.getenv('STRIPE_SECRET_KEY', ''),
        STRIPE_WEBHOOK_SECRET=os.getenv('STRIPE_WEBHOOK_SECRET', ''),
        STRIPE_PRICE_STARTER=os.getenv('STRIPE_PRICE_STARTER', ''),
        STRIPE_PRICE_PRO=os.getenv('STRIPE_PRICE_PRO', ''),
        STRIPE_PRICE_STUDIO=os.getenv('STRIPE_PRICE_STUDIO', ''),
        STRIPE_PRICE_LIFETIME=os.getenv('STRIPE_PRICE_LIFETIME', ''),
        GOOGLE_CLIENT_ID=os.getenv('GOOGLE_CLIENT_ID', ''),
        GOOGLE_CLIENT_SECRET=os.getenv('GOOGLE_CLIENT_SECRET', ''),
        GOOGLE_DEV_EMAIL=os.getenv('GOOGLE_DEV_EMAIL', 'demo@colorfulme.app'),
        RESEND_API_KEY=os.getenv('RESEND_API_KEY', ''),
        RESEND_FROM_EMAIL=os.getenv('RESEND_FROM_EMAIL', ''),
    )

    # Ensure absolute manifest path for deterministic loading.
    manifest_path = app.config['PROGRAMMATIC_CONTENT_MANIFEST']
    if not os.path.isabs(manifest_path):
        app.config['PROGRAMMATIC_CONTENT_MANIFEST'] = os.path.join(project_root, manifest_path)

    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(os.path.join(app.instance_path, 'generated'), exist_ok=True)

    logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO').upper())

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'web.index'
    login_manager.session_protection = 'strong'

    from models import User

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, user_id)

    @login_manager.request_loader
    def load_user_from_request(_request):
        return None

    @app.context_processor
    def inject_globals():
        from colorfulme.services.programmatic_service import ProgrammaticService

        tools = [
            entry
            for entry in ProgrammaticService.get_entries_by_type('tool')
            if entry.get('status') == 'published'
        ]
        by_path = {}
        for entry in tools:
            route_path = entry.get('route_path')
            if route_path and route_path not in by_path:
                by_path[route_path] = entry

        prompt_routes = [
            '/prompt-generators/midjourney-prompt-generator',
            '/prompt-generators/flux-prompt-generator',
            '/prompt-generators/stable-diffusion-prompt-generator',
            '/prompt-generators/image-prompt-generator',
            '/prompt-generators/drawing-prompt-generator',
            '/prompt-generators/image-to-prompt-generator',
            '/prompt-generators/recraft-prompt-generator',
        ]
        core_routes = [
            '/ai-coloring-page-generator',
            '/photo-to-coloring-page-converter',
            '/photo-to-sketch',
            '/family-photo-coloring-page',
            '/coloring-book-generator',
            '/generators/name-coloring-page-generator',
            '/generators/bible-verse-coloring-page-generator',
            '/generators/quote-coloring-page-generator',
            '/generators/bubble-letter-coloring-page-generator',
            '/generators/graffiti-coloring-page-generator',
            '/generators/rainy-day-activities',
            '/generators/classroom-activities',
        ]

        nav_generators_prompt = [by_path[path] for path in prompt_routes if path in by_path]
        nav_generators_core = [by_path[path] for path in core_routes if path in by_path]
        generator_paths = sorted(by_path.keys())

        free_entries = []
        for entry in ProgrammaticService.get_entries_by_type('page'):
            if entry.get('status') != 'published':
                continue
            route_path = str(entry.get('route_path', ''))
            if route_path.startswith('/free-coloring-pages/') and route_path.count('/') == 2:
                free_entries.append(entry)

        free_entries.sort(key=lambda item: (item.get('title') or '').lower())
        age_routes = [
            '/free-coloring-pages/for-kids',
            '/free-coloring-pages/for-teens',
            '/free-coloring-pages/for-adults',
            '/free-coloring-pages/for-seniors',
            '/free-coloring-pages/for-toddlers',
            '/free-coloring-pages/for-preschoolers',
            '/free-coloring-pages/for-tweens',
        ]
        free_by_path = {
            entry.get('route_path'): entry
            for entry in free_entries
            if entry.get('route_path')
        }
        nav_free_ages = [free_by_path[path] for path in age_routes if path in free_by_path]
        nav_free_featured = [entry for entry in free_entries if entry.get('route_path') not in set(age_routes)][:18]

        return {
            'app_brand_name': app.config['APP_BRAND_NAME'],
            'nav_generators_core': nav_generators_core,
            'nav_generators_prompt': nav_generators_prompt,
            'nav_generator_paths': generator_paths,
            'nav_generators_core_count': len(nav_generators_core),
            'nav_generators_prompt_count': len(nav_generators_prompt),
            'nav_free_ages': nav_free_ages,
            'nav_free_featured': nav_free_featured,
            'nav_free_categories_count': len(free_entries),
        }

    from colorfulme.blueprints.auth import auth_bp
    from colorfulme.blueprints.billing import billing_bp
    from colorfulme.blueprints.web import web_bp
    from colorfulme.blueprints.api import api_bp
    from colorfulme.blueprints.seo import seo_bp

    # Register deterministic/static routes before catch-all SEO routes.
    app.register_blueprint(web_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(seo_bp)

    with app.app_context():
        from colorfulme.services.credits_service import seed_default_plans

        db.create_all()
        seed_default_plans()

    return app
