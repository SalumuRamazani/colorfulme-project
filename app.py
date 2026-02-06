from flask import Flask, render_template, request, Response, redirect, url_for, session as flask_session, make_response, jsonify
from datetime import datetime, timedelta
from werkzeug.middleware.proxy_fix import ProxyFix
import os
import logging
import stripe
import json
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from programmatic_content import (
    DEFAULT_MANIFEST_PATH as PROGRAMMATIC_DEFAULT_MANIFEST_PATH,
    build_published_route_index,
    load_manifest,
)

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

DEFAULT_SESSION_SECRET = 'dev-secret-key-CHANGE-IN-PRODUCTION'
DEFAULT_DATABASE_URL = 'sqlite:///receiptforge.db'

# Configure logging
logging.basicConfig(level=os.environ.get('LOG_LEVEL', 'INFO').upper())

# Configure Stripe API key globally
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '').strip()

# Import extensions
from extensions import db, login_manager
from templates_data import TEMPLATES, CATEGORIES, get_template_by_slug, get_templates_by_category, CATEGORY_HUBS, get_hub_by_slug, get_all_hubs


def create_app():
    """Application factory pattern"""
    app = Flask(__name__)
    
    # Configuration
    app.secret_key = os.environ.get("SESSION_SECRET", DEFAULT_SESSION_SECRET)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    database_url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        'pool_pre_ping': True,
        "pool_recycle": 300,
    }
    app.config["DEBUG"] = os.environ.get("DEBUG", "false").lower() == "true"

    programmatic_manifest_path = os.environ.get(
        "PROGRAMMATIC_CONTENT_MANIFEST",
        PROGRAMMATIC_DEFAULT_MANIFEST_PATH,
    )
    if not os.path.isabs(programmatic_manifest_path):
        programmatic_manifest_path = os.path.join(app.root_path, programmatic_manifest_path)

    programmatic_manifest = load_manifest(programmatic_manifest_path)
    programmatic_route_index = build_published_route_index(programmatic_manifest)
    logging.info(
        "Programmatic content loaded: %s published routes from %s",
        len(programmatic_route_index),
        programmatic_manifest_path,
    )
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    
    # Lazy initialization flag
    _initialized = {'db': False}
    
    def init_database():
        """Initialize database tables and webhooks lazily on first request"""
        if _initialized['db']:
            return
        
        _initialized['db'] = True
        
        try:
            # Import models to register them
            import models
            from models import User, Subscription, IncomingWebhookConfig
            db.create_all()
            logging.info("Database tables created")
            
            # Initialize site-wide incoming webhook for Outrank integration
            try:
                # First ensure SITE user exists
                site_user = User.query.filter_by(id='SITE').first()
                if not site_user:
                    site_user = User(
                        id='SITE',
                        email='site@receiptmake.com',
                        first_name='ReceiptMake',
                        last_name='Site'
                    )
                    db.session.add(site_user)
                    db.session.commit()
                    logging.info("Created SITE system user")
                
                # Ensure OUTRANK user exists for Outrank webhook
                outrank_user = User.query.filter_by(id='OUTRANK').first()
                if not outrank_user:
                    outrank_user = User(
                        id='OUTRANK',
                        email='outrank@receiptmake.com',
                        first_name='Outrank',
                        last_name='Integration'
                    )
                    db.session.add(outrank_user)
                    db.session.commit()
                    logging.info("Created OUTRANK system user")
                
                # Now create/check site-wide webhook
                site_webhook = IncomingWebhookConfig.query.filter_by(public_id='site-outrank-webhook').first()
                if not site_webhook:
                    # Create the site-wide webhook configuration
                    import uuid
                    import secrets
                    import hashlib
                    
                    api_key = secrets.token_urlsafe(32)
                    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
                    api_key_hint = api_key[-4:]
                    
                    # Use a special user_id 'SITE' for site-wide webhooks
                    site_webhook = IncomingWebhookConfig(
                        user_id='SITE',
                        public_id='site-outrank-webhook',
                        api_key_hash=api_key_hash,
                        api_key_hint=api_key_hint,
                        is_active=True
                    )
                    db.session.add(site_webhook)
                    db.session.commit()
                    
                    # Store the API key securely in an environment variable for first-time setup
                    # This will only be accessible via the admin endpoint
                    logging.info(f"✅ SITE-WIDE WEBHOOK CREATED!")
                    logging.info(f"📍 Webhook URL: /api/incoming/webhooks/site-outrank-webhook")
                    logging.info(f"🔐 API Key hint: ...{api_key_hint}")
                    logging.info(f"💡 Access full credentials via /admin/webhook-config endpoint (requires authentication)")
                else:
                    logging.info("Site-wide webhook already exists")
                
                # Create/check Outrank-specific webhook with provided public_id
                outrank_webhook = IncomingWebhookConfig.query.filter_by(public_id='3009a3c0-481d-424a-8ac0-f7306f363179').first()
                if not outrank_webhook:
                    import hashlib
                    
                    # Use the specific API key configured for Outrank
                    api_key = '2U26PfXMgvdWqwwN7gLHSbFDCC3tHAumAoF-N86lUJs'
                    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
                    api_key_hint = api_key[-4:]
                    
                    outrank_webhook = IncomingWebhookConfig(
                        user_id='OUTRANK',  # Separate system user for Outrank webhook
                        public_id='3009a3c0-481d-424a-8ac0-f7306f363179',
                        api_key_hash=api_key_hash,
                        api_key_hint=api_key_hint,
                        is_active=True
                    )
                    db.session.add(outrank_webhook)
                    db.session.commit()
                    
                    logging.info(f"✅ OUTRANK WEBHOOK CREATED!")
                    logging.info(f"📍 Webhook URL: /api/incoming/webhooks/3009a3c0-481d-424a-8ac0-f7306f363179")
                    logging.info(f"🔐 API Key hint: ...{api_key_hint}")
                    logging.info(f"💡 Use this webhook URL in your Outrank dashboard to receive blog post updates")
                else:
                    logging.info("Outrank webhook already exists")
            except Exception as e:
                logging.warning(f"Could not initialize site webhook: {str(e)}")
        except Exception as e:
            logging.error(f"Database initialization error: {str(e)}")
    
    # Initialize database on first request (except health check)
    @app.before_request
    def before_request():
        if request.endpoint != 'health_check':
            with app.app_context():
                init_database()
    
    # Import Flask-Login decorators
    from flask_login import current_user, login_required

    # User loader for Flask-Login (REQUIRED).
    # Register directly on app.login_manager to avoid missing callback in mixed import contexts.
    def load_user(user_id):
        from models import User
        return User.query.get(user_id)

    app.login_manager.user_loader(load_user)

    @app.login_manager.request_loader
    def load_user_from_request(_request):
        return None

    # TODO: Implement custom authentication system
    # Replit Auth removed - add your preferred auth method here
    # Options: Flask-Login with email/password, OAuth (Google, GitHub), etc.

    # Context processor for current_user
    @app.context_processor
    def inject_user():
        return dict(current_user=current_user)
    
    # Make session permanent
    @app.before_request
    def make_session_permanent():
        flask_session.permanent = True
    
    # Auto-save pending templates when user logs in
    @app.before_request
    def auto_save_pending_template():
        """Auto-save pending template after user logs in"""
        if current_user.is_authenticated:
            pending_receipt = flask_session.get('pending_template_save')
            if pending_receipt and isinstance(pending_receipt, dict):
                try:
                    from models import SavedTemplate
                    import json
                    
                    # SECURITY: Validate session ID matches
                    current_session_id = flask_session.get('_id')
                    receipt_session_id = pending_receipt.get('session_id')
                    if not current_session_id or not receipt_session_id or current_session_id != receipt_session_id:
                        logging.warning(f"Session ID mismatch - skipping auto-save")
                        flask_session.pop('pending_template_save', None)
                        return
                    
                    # Validate timestamp (only save if receipt is recent - within 1 hour)
                    timestamp = pending_receipt.get('timestamp')
                    if timestamp:
                        receipt_age = datetime.now().timestamp() * 1000 - timestamp
                        if receipt_age > 3600000:  # 1 hour in milliseconds
                            logging.warning(f"Pending receipt too old ({receipt_age}ms), skipping auto-save")
                            flask_session.pop('pending_template_save', None)
                            return
                    
                    # Extract config - handle both dict and JSON string
                    config = pending_receipt.get('config')
                    if isinstance(config, str):
                        config = json.loads(config)
                    elif not isinstance(config, dict):
                        config = {}
                    
                    # Validate config is not empty
                    if not config:
                        logging.warning("Pending receipt has empty config, skipping auto-save")
                        flask_session.pop('pending_template_save', None)
                        return
                    
                    # Sanitize name and description
                    import bleach
                    name = bleach.clean(str(pending_receipt.get('name', 'Auto-saved Receipt')), tags=[], strip=True)[:100]
                    description = bleach.clean(str(pending_receipt.get('description', 'Saved after signup')), tags=[], strip=True)[:500]
                    
                    # Check if template already exists (prevent duplicates)
                    existing = SavedTemplate.query.filter_by(
                        user_id=current_user.id,
                        name=name
                    ).first()
                    
                    if not existing:
                        # Create the template
                        template = SavedTemplate(
                            user_id=current_user.id,
                            name=name,
                            description=description,
                            template_type='custom',
                            config_json=json.dumps(config)
                        )
                        db.session.add(template)
                        db.session.commit()
                        logging.info(f"✅ Auto-saved pending receipt as template {template.id} for user {current_user.id}")
                    
                    # Clear the pending receipt from session
                    flask_session.pop('pending_template_save', None)
                    
                    # Set a flag to redirect to dashboard and show success
                    flask_session['show_autosave_success'] = True
                    flask_session['redirect_to_dashboard_after_autosave'] = True
                    
                except Exception as e:
                    logging.error(f"❌ Error auto-saving pending receipt on login: {str(e)}", exc_info=True)
                    # Clear stale pending receipt to prevent future attempts
                    flask_session.pop('pending_template_save', None)
    
        # SEO: Redirect legacy URLs with apostrophes and broken category pages
    @app.before_request
    def handle_legacy_redirects():
        """Handle 301 redirects for old URLs to prevent 404s and improve SEO"""
        path = request.path
        
        # Redirect map for apostrophe URLs and other legacy patterns
        # All category hub pages have been removed, redirecting them to filtered template views
        redirects = {
            # Apostrophe in template detail URLs
            "/template/Lowe's-Receipt": "/template/Lowes-Receipt",
            "/template/McDonald's-Receipt": "/template/McDonalds-Receipt",
            # Hub Pages Redirects
            "/templates/retail": "/templates?category=Retail",
            "/templates/grocery": "/templates?category=Grocery",
            "/templates/restaurant": "/templates?category=Restaurant",
            "/templates/gas-station": "/templates?category=Gas Station",
            "/templates/luxury": "/templates?category=Luxury",
            "/templates/service": "/templates?category=Service",
            "/templates/automotive": "/templates?category=Automotive",
            "/templates/hospitality": "/templates?category=Hospitality",
            "/templates/transportation": "/templates?category=Transportation",
            "/templates/generic": "/templates?category=Generic",
            "/templates/hotel": "/templates?category=Hospitality",
            # Other broken category pages
            "/templates/sales": "/templates?category=Retail",
            "/templates/parking": "/templates?category=Transportation",
            "/templates/itemized": "/templates?category=Retail",
            "/templates/simple-receipt-template": "/templates",
            "/templates/cash": "/templates?category=Retail",
            "/templates/cash-payment-receipt-template": "/templates",
            "/templates/donation-receipt-template": "/templates",
            "/templates/general-receipt-template": "/templates",
            "/templates/service-receipt-template": "/templates",
            "/templates/simple-cash-receipt-template": "/templates",
            "/templates/cash-receipt-template": "/templates",
            # Old template names that don't exist
            "/template/Simple-Sales-Receipt": "/templates?category=Retail",
            "/template/Retail-Store-Receipt": "/templates?category=Retail",
            "/template/Cash-Receipt": "/templates?category=Retail",
            "/template/Donation-Receipt": "/templates",
            "/template/Service-Receipt": "/templates?category=Services",
            "/template/freight-delivery-receipt": "/templates?category=Transportation",
        }
        
        if path in redirects:
            return redirect(redirects[path], code=301)
        
        return None
    
    # Performance: Add cache headers for static assets
    @app.after_request
    def add_cache_headers(response):
        """Add cache headers for static assets and disable caching for dynamic HTML"""
        # Disable cache for HTML pages (template landing pages, receipts, etc)
        if request.path.endswith('.html') or not request.path.startswith('/static/'):
            # For non-static routes (HTML pages), disable caching
            if response.content_type and 'text/html' in response.content_type:
                response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, public, max-age=0'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '0'
        
        # Cache static files
        if request.path.startswith('/static/'):
            # Add CORS headers for images (needed for html2canvas)
            if any(request.path.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp', '.svg']):
                response.headers['Access-Control-Allow-Origin'] = '*'
                response.headers['Cross-Origin-Resource-Policy'] = 'cross-origin'
            
            # Shorter cache for CSS/JS (1 week) since they're not fingerprinted
            if any(request.path.endswith(ext) for ext in ['.css', '.js']):
                response.cache_control.max_age = 604800  # 1 week
                response.cache_control.public = True
                response.headers['Vary'] = 'Accept-Encoding'
            # Long cache for images and fonts (1 year) - content rarely changes
            elif any(request.path.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp', '.woff', '.woff2', '.ttf', '.svg']):
                response.cache_control.max_age = 31536000  # 1 year
                response.cache_control.public = True
                response.headers['Vary'] = 'Accept-Encoding'
        return response
    
    # Routes
    @app.route('/health')
    def health_check():
        """Health check endpoint for deployment"""
        return {'status': 'healthy', 'timestamp': datetime.now().isoformat()}, 200
    
    @app.route('/blog/how-to-make-a-receipt-online')
    def redirect_blog_post():
        return redirect(url_for('index'), code=301)

    @app.route('/')
    def index():
        featured_templates = TEMPLATES[:8]
        return render_template('index.html', templates=featured_templates)

    @app.route('/templates')
    def templates_page():
        category = request.args.get('category', 'All')
        sort_by = request.args.get('sort', 'newest')
        
        templates = get_templates_by_category(category)
        
        if sort_by == 'oldest':
            templates = list(reversed(templates))
        elif sort_by == 'name-asc':
            templates = sorted(templates, key=lambda x: x['name'])
        elif sort_by == 'name-desc':
            templates = sorted(templates, key=lambda x: x['name'], reverse=True)
        
        return render_template('templates.html', 
                             templates=templates, 
                             categories=CATEGORIES,
                             current_category=category,
                             current_sort=sort_by)

    @app.route('/template/<slug>')
    def template_detail(slug):
        template = get_template_by_slug(slug)
        if not template:
            return "Template not found", 404
        
        related_templates = [t for t in TEMPLATES if t['category'] == template['category'] and t['id'] != template['id']][:3]
        
        return render_template('template_detail.html', 
                             template=template,
                             related_templates=related_templates)

    @app.route('/auth-generate/<template_id>')
    def auth_generate(template_id):
        """No longer authentication-protected as per user request.
        Redirects directly to the generator."""
        # Build the target generator URL
        generator_url = f"/generate-{template_id}-receipt"
        
        # User is authenticated, redirect to generator
        return redirect(generator_url)

    @app.route('/privacy-policy')
    def privacy_policy():
        return render_template('privacy_policy.html')

    @app.route('/invoice-generator')
    def invoice_generator():
        return render_template('invoice_generator.html')

    def load_template_config(template_name):
        """Load receipt template configuration from JSON file"""
        import json
        import os
        
        template_path = os.path.join(app.static_folder, 'data', f'{template_name}_receipt_template.json')
        if not os.path.exists(template_path):
            return None
        
        try:
            with open(template_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            app.logger.error(f"Failed to load template {template_name}: {str(e)}")
            return None
    
    @app.route('/generate-advanced')
    def generate_advanced():
        """Modular receipt generator V2 with drag-and-drop sections - defaults to Convenience Store template"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        template_config = None
        load_error = None
        load_template_id = request.args.get('load_template')
        
        if load_template_id and current_user and current_user.is_authenticated:
            from models import SavedTemplate
            try:
                saved_template = SavedTemplate.query.filter_by(
                    id=load_template_id,
                    user_id=current_user.id
                ).first()
                
                if saved_template:
                    template_config = saved_template.config_json
                    logging.info(f"Loaded template {load_template_id} for user {current_user.id}")
                else:
                    load_error = "Template not found or access denied"
                    logging.warning(f"Template {load_template_id} not found for user {current_user.id}")
            except Exception as e:
                load_error = "Failed to load template"
                logging.error(f"Error loading template {load_template_id}: {str(e)}")
        else:
            # Load ace (ACE Hardware) template by default
            template_config = load_template_config('ace')
        
        return render_template('generate_advanced_v2.html', has_subscription=has_subscription, template_config=template_config, load_error=load_error)
    
    # Template ID to JSON filename mapping
    # Note: Keys are the slug part from /generate-<slug>-receipt URLs
    TEMPLATE_JSON_MAP = {
        'example': 'example',
        'restaurant-bill': 'generic_restaurant',
        'hotel': 'generic_hotel',
        'gas': 'generic_gas',
        'generic-pos': 'generic_pos',
        'hilton-hotel': 'hilton',
        'motel6': 'motel6',
        'neimanmarcus': 'neimanmarcus',
        'pawnshop': 'pawnshop',
        'tire-shop': 'tire_shop',
        'oil-change': 'oil_change',
        'tmobile': 'tmobile',
        'dollar-tree': 'dollar_tree',
        'cvs-pharmacy': 'cvs',
        'best-buy': 'bestbuy',
        'costco-wholesale': 'costco',
        'mcdonalds': 'mcdonalds',
        'chickfila': 'chickfila',
        'chick-fil-a': 'chickfila',
        'grocery-store': 'grocery_store',
        'grocery': 'grocery_store',
        'saks': 'saks',
        'saks-fifth-avenue': 'saks',
        'albertsons': 'albertsons',
        'lowes': 'lowes',
        'kroger': 'kroger',
        'subway': 'subway',
        'starbucks': 'starbucks',
        'target': 'target',
        'walmart': 'walmart',
        'shell': 'shell',
        'chevron': 'chevron',
        'bp': 'bp',
        'walgreens': 'walgreens',
        'safeway': 'safeway',
        'popeyes': 'popeyes',
        'uber': 'uber',
        'gucci': 'gucci',
        'rolex': 'rolex',
        'dior': 'dior',
        'chanel': 'chanel',
        'cartier': 'cartier',
        'burberry': 'burberry',
        'stockx': 'stockx',
        'goat': 'goat',
        'parking': 'parking',
        'taxi': 'taxi',
        'courier': 'courier_service',
        'moving': 'moving',
        'autozone': 'autozone',
        'ace': 'ace',
        'convenience-store': 'convenience_store',
        'roofing': 'roofing',
        'summer-camp': 'summer_camp',
        'storage': 'storage',
        'electrician': 'electrician',
        'carwash': 'carwash',
        'carental': 'carental',
        'therapy': 'therapy',
        'oilchange': 'oilchange',
        'cardetailing': 'cardetailing',
        'vet': 'vet',
        'service': 'service',
        'auto-repair': 'auto_repair',
        'computer-repair': 'computer_repair',
        'neiman-marcus': 'neimanmarcus',
        'pawn-shop': 'pawnshop',
        't-mobile': 'tmobile',
        'motel-6': 'motel6',
        'generic-restaurant': 'generic_restaurant'
    }
    
    @app.route('/generate-<slug>-receipt')
    def generate_receipt(slug):
        """Dynamic route for all receipt templates"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Map template ID to JSON filename
        template_key = TEMPLATE_JSON_MAP.get(slug, slug.replace('-', '_'))
        
        template_config = load_template_config(template_key)
        if not template_config:
            app.logger.warning(f"Template not found: slug='{slug}', template_key='{template_key}'")
            return f"Template '{slug}' not found", 404
        
        template_name = template_config.get('name', f'{slug.replace("-", " ").title()} Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=template_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-target-receipt')
    def generate_target_receipt():
        """Pre-configured Target receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load Target template from JSON file
        target_config = load_template_config('target')
        if not target_config:
            return "Target template not found", 404
        
        template_name = target_config.get('name', 'Target Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=target_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-starbucks-receipt')
    def generate_starbucks_receipt():
        """Pre-configured Starbucks receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load Starbucks template from JSON file
        starbucks_config = load_template_config('starbucks')
        if not starbucks_config:
            return "Starbucks template not found", 404
        
        template_name = starbucks_config.get('name', 'Starbucks Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=starbucks_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-walmart-receipt')
    def generate_walmart_receipt():
        """Pre-configured Walmart receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load Walmart template from JSON file
        walmart_config = load_template_config('walmart')
        if not walmart_config:
            return "Walmart template not found", 404
        
        template_name = walmart_config.get('name', 'Walmart Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=walmart_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/walmart-receipt')
    def walmart_receipt_landing():
        """Walmart receipt landing page - redirects to template detail"""
        return redirect(url_for('template_detail', slug='Walmart-Receipt'))
    
    @app.route('/courier-service-receipt')
    def courier_service_landing():
        """Courier service receipt landing page"""
        return render_template('courier_service_landing.html')
    
    @app.route('/moving-receipt')
    def moving_receipt_landing():
        """Moving receipt landing page"""
        return render_template('moving_company_landing.html')
    
    @app.route('/autozone-receipt')
    def autozone_landing():
        """AutoZone receipt landing page"""
        return render_template('autozone_landing.html')
    
    @app.route('/ace-receipt')
    def ace_landing():
        """ACE Hardware receipt landing page"""
        return render_template('ace_landing.html')
    
    @app.route('/convenience-store-receipt')
    def convenience_store_landing():
        """Convenience store receipt landing page"""
        return render_template('convenience_store_landing.html')
    
    @app.route('/roofing-receipt')
    def roofing_landing():
        """Roofing service receipt landing page"""
        return render_template('roofing_landing.html')
    
    @app.route('/summer-camp-receipt')
    def summer_camp_landing():
        """Summer camp receipt landing page"""
        return render_template('summer_camp_landing.html')
    
    @app.route('/storage-receipt')
    def storage_landing():
        """Storage facility receipt landing page"""
        return render_template('storage_landing.html')
    
    @app.route('/electrician-receipt')
    def electrician_landing():
        """Electrician service receipt landing page"""
        return render_template('electrician_landing.html')
    
    @app.route('/carwash-receipt')
    def carwash_landing():
        """Car wash service receipt landing page"""
        return render_template('carwash_landing.html')
    
    @app.route('/carental-receipt')
    def carental_landing():
        """Car rental receipt landing page"""
        return render_template('carental_landing.html')
    
    @app.route('/therapy-receipt')
    def therapy_landing():
        """Therapy session receipt landing page"""
        return render_template('therapy_landing.html')
    
    @app.route('/oilchange-receipt')
    def oilchange_landing():
        """Oil change service receipt landing page"""
        return render_template('oilchange_landing.html')
    
    @app.route('/cardetailing-receipt')
    def cardetailing_landing():
        """Car detailing service receipt landing page"""
        return render_template('cardetailing_landing.html')
    
    @app.route('/vet-receipt')
    def vet_landing():
        """Veterinary service receipt landing page"""
        return render_template('vet_landing.html')
    
    @app.route('/generate-roofing-receipt')
    def generate_roofing_receipt():
        """Pre-configured Roofing receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        roofing_config = load_template_config('roofing')
        if not roofing_config:
            return "Roofing template not found", 404
        
        template_name = roofing_config.get('name', 'Roofing Service Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=roofing_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-summer-camp-receipt')
    def generate_summer_camp_receipt():
        """Pre-configured Summer Camp receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        summer_camp_config = load_template_config('summer_camp')
        if not summer_camp_config:
            return "Summer Camp template not found", 404
        
        template_name = summer_camp_config.get('name', 'Summer Camp Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=summer_camp_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-storage-receipt')
    def generate_storage_receipt():
        """Pre-configured Storage Facility receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        storage_config = load_template_config('storage')
        if not storage_config:
            return "Storage template not found", 404
        
        template_name = storage_config.get('name', 'Storage Facility Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=storage_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-electrician-receipt')
    def generate_electrician_receipt():
        """Pre-configured Electrician receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        electrician_config = load_template_config('electrician')
        if not electrician_config:
            return "Electrician template not found", 404
        
        template_name = electrician_config.get('name', 'Electrician Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=electrician_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-carwash-receipt')
    def generate_carwash_receipt():
        """Pre-configured Car Wash receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        carwash_config = load_template_config('carwash')
        if not carwash_config:
            return "Car Wash template not found", 404
        
        template_name = carwash_config.get('name', 'Car Wash Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=carwash_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-carental-receipt')
    def generate_carental_receipt():
        """Pre-configured Car Rental receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        carental_config = load_template_config('carental')
        if not carental_config:
            return "Car Rental template not found", 404
        
        template_name = carental_config.get('name', 'Car Rental Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=carental_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-therapy-receipt')
    def generate_therapy_receipt():
        """Pre-configured Therapy receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        therapy_config = load_template_config('therapy')
        if not therapy_config:
            return "Therapy template not found", 404
        
        template_name = therapy_config.get('name', 'Therapy Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=therapy_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-oilchange-receipt')
    def generate_oilchange_receipt():
        """Pre-configured Oil Change receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        oilchange_config = load_template_config('oilchange')
        if not oilchange_config:
            return "Oil Change template not found", 404
        
        template_name = oilchange_config.get('name', 'Oil Change Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=oilchange_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-cardetailing-receipt')
    def generate_cardetailing_receipt():
        """Pre-configured Car Detailing receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        cardetailing_config = load_template_config('cardetailing')
        if not cardetailing_config:
            return "Car Detailing template not found", 404
        
        template_name = cardetailing_config.get('name', 'Car Detailing Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=cardetailing_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-vet-receipt')
    def generate_vet_receipt():
        """Pre-configured Vet receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        vet_config = load_template_config('vet')
        if not vet_config:
            return "Vet template not found", 404
        
        template_name = vet_config.get('name', 'Vet Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=vet_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/service-receipt')
    def service_landing():
        """Service receipt landing page"""
        return render_template('service_landing.html')
    
    @app.route('/auto-repair-receipt')
    def auto_repair_landing():
        """Auto repair receipt landing page"""
        return render_template('auto_repair_landing.html')
    
    @app.route('/computer-repair-receipt')
    def computer_repair_landing():
        """Computer repair receipt landing page"""
        return render_template('computer_repair_landing.html')
    
    @app.route('/generate-cvs-pharmacy-receipt')
    def generate_cvs_pharmacy_receipt():
        """Pre-configured CVS Pharmacy receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load CVS template from JSON file
        cvs_config = load_template_config('cvs')
        if not cvs_config:
            return "CVS Pharmacy template not found", 404
        
        template_name = cvs_config.get('name', 'CVS Pharmacy Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=cvs_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-best-buy-receipt')
    def generate_best_buy_receipt():
        """Pre-configured Best Buy receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load Best Buy template from JSON file
        bestbuy_config = load_template_config('bestbuy')
        if not bestbuy_config:
            return "Best Buy template not found", 404
        
        template_name = bestbuy_config.get('name', 'Best Buy Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=bestbuy_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-costco-receipt')
    def generate_costco_receipt():
        """Pre-configured Costco receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load Costco template from JSON file
        costco_config = load_template_config('costco')
        if not costco_config:
            return "Costco template not found", 404
        
        template_name = costco_config.get('name', 'Costco Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=costco_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-kroger-receipt')
    def generate_kroger_receipt():
        """Pre-configured Kroger receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load Kroger template from JSON file
        kroger_config = load_template_config('kroger')
        if not kroger_config:
            return "Kroger template not found", 404
        
        template_name = kroger_config.get('name', 'Kroger Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=kroger_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-albertsons-receipt')
    def generate_albertsons_receipt():
        """Pre-configured Albertsons receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load Albertsons template from JSON file
        albertsons_config = load_template_config('albertsons')
        if not albertsons_config:
            return "Albertsons template not found", 404
        
        template_name = albertsons_config.get('name', 'Albertsons Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=albertsons_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-lowes-receipt')
    def generate_lowes_receipt():
        """Pre-configured Lowe's receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load Lowe's template from JSON file
        lowes_config = load_template_config('lowes')
        if not lowes_config:
            return "Lowe's template not found", 404
        
        template_name = lowes_config.get('name', "Lowe's Receipt")
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=lowes_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-mcdonalds-receipt')
    def generate_mcdonalds_receipt():
        """Pre-configured McDonald's receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load McDonald's template from JSON file
        mcdonalds_config = load_template_config('mcdonalds')
        if not mcdonalds_config:
            return "McDonald's template not found", 404
        
        template_name = mcdonalds_config.get('name', "McDonald's Receipt")
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=mcdonalds_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-subway-receipt')
    def generate_subway_receipt():
        """Pre-configured Subway receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load Subway template from JSON file
        subway_config = load_template_config('subway')
        if not subway_config:
            return "Subway template not found", 404
        
        template_name = subway_config.get('name', 'Subway Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=subway_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-walgreens-receipt')
    def generate_walgreens_receipt():
        """Pre-configured Walgreens receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load Walgreens template from JSON file
        walgreens_config = load_template_config('walgreens')
        if not walgreens_config:
            return "Walgreens template not found", 404
        
        template_name = walgreens_config.get('name', 'Walgreens Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=walgreens_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-shell-receipt')
    def generate_shell_receipt():
        """Pre-configured Shell receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load Shell template from JSON file
        shell_config = load_template_config('shell')
        if not shell_config:
            return "Shell template not found", 404
        
        template_name = shell_config.get('name', 'Shell Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=shell_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-popeyes-receipt')
    def generate_popeyes_receipt():
        """Pre-configured Popeyes receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load Popeyes template from JSON file
        popeyes_config = load_template_config('popeyes')
        if not popeyes_config:
            return "Popeyes template not found", 404
        
        template_name = popeyes_config.get('name', 'Popeyes Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=popeyes_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-uber-receipt')
    def generate_uber_receipt():
        """Pre-configured Uber receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load Uber template from JSON file
        uber_config = load_template_config('uber')
        if not uber_config:
            return "Uber template not found", 404
        
        template_name = uber_config.get('name', 'Uber Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=uber_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-hilton-receipt')
    def generate_hilton_receipt():
        """Pre-configured Hilton receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load Hilton template from JSON file
        hilton_config = load_template_config('hilton')
        if not hilton_config:
            return "Hilton template not found", 404
        
        template_name = hilton_config.get('name', 'Hilton Hotel Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=hilton_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-dollar-tree-receipt')
    def generate_dollar_tree_receipt():
        """Pre-configured Dollar Tree receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load Dollar Tree template from JSON file
        dollar_tree_config = load_template_config('dollar_tree')
        if not dollar_tree_config:
            return "Dollar Tree template not found", 404
        
        template_name = dollar_tree_config.get('name', 'Dollar Tree Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=dollar_tree_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-chevron-receipt')
    def generate_chevron_receipt():
        """Pre-configured Chevron receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load Chevron template from JSON file
        chevron_config = load_template_config('chevron')
        if not chevron_config:
            return "Chevron template not found", 404
        
        template_name = chevron_config.get('name', 'Chevron Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=chevron_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-gucci-receipt')
    def generate_gucci_receipt():
        """Pre-configured Gucci receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load Gucci template from JSON file
        gucci_config = load_template_config('gucci')
        if not gucci_config:
            return "Gucci template not found", 404
        
        template_name = gucci_config.get('name', 'Gucci Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=gucci_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-bp-receipt')
    def generate_bp_receipt():
        """Pre-configured BP gas station receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load BP template from JSON file
        bp_config = load_template_config('bp')
        if not bp_config:
            return "BP template not found", 404
        
        template_name = bp_config.get('name', 'BP Gas Station Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=bp_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-verizon-receipt')
    def generate_verizon_receipt():
        """Pre-configured Verizon receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        verizon_config = load_template_config('verizon')
        if not verizon_config:
            return "Verizon template not found", 404
        
        template_name = verizon_config.get('name', 'Verizon Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=verizon_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-dentist-receipt')
    def generate_dentist_receipt():
        """Pre-configured Dentist receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        dentist_config = load_template_config('dentist')
        if not dentist_config:
            return "Dentist template not found", 404
        
        template_name = dentist_config.get('name', 'Dentist Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=dentist_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-doctor-receipt')
    def generate_doctor_receipt():
        """Pre-configured Doctor receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        doctor_config = load_template_config('doctor')
        if not doctor_config:
            return "Doctor template not found", 404
        
        template_name = doctor_config.get('name', 'Doctor Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=doctor_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-tutoring-receipt')
    def generate_tutoring_receipt():
        """Pre-configured Tutoring receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        tutoring_config = load_template_config('tutoring')
        if not tutoring_config:
            return "Tutoring template not found", 404
        
        template_name = tutoring_config.get('name', 'Tutoring Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=tutoring_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-bakery-receipt')
    def generate_bakery_receipt():
        """Pre-configured Bakery receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        bakery_config = load_template_config('bakery')
        if not bakery_config:
            return "Bakery template not found", 404
        
        template_name = bakery_config.get('name', 'Bakery Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=bakery_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-safeway-receipt')
    def generate_safeway_receipt():
        """Pre-configured Safeway grocery receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load Safeway template from JSON file
        safeway_config = load_template_config('safeway')
        if not safeway_config:
            return "Safeway template not found", 404
        
        template_name = safeway_config.get('name', 'Safeway Grocery Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=safeway_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-tmobile-receipt')
    def generate_tmobile_receipt():
        """Pre-configured T-Mobile receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load T-Mobile template from JSON file
        tmobile_config = load_template_config('tmobile')
        if not tmobile_config:
            return "T-Mobile template not found", 404
        
        template_name = tmobile_config.get('name', 'T-Mobile Store Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=tmobile_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-parking-receipt')
    def generate_parking_receipt():
        """Pre-configured parking receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load parking template from JSON file
        parking_config = load_template_config('parking')
        if not parking_config:
            return "Parking template not found", 404
        
        template_name = parking_config.get('name', 'Parking Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=parking_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-taxi-receipt')
    def generate_taxi_receipt():
        """Pre-configured taxi receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load taxi template from JSON file
        taxi_config = load_template_config('taxi')
        if not taxi_config:
            return "Taxi template not found", 404
        
        template_name = taxi_config.get('name', 'Taxi Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=taxi_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-oil-change-receipt')
    def generate_oil_change_receipt():
        """Pre-configured oil change service receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load oil change template from JSON file
        oil_change_config = load_template_config('oil_change')
        if not oil_change_config:
            return "Oil Change template not found", 404
        
        template_name = oil_change_config.get('name', 'Oil Change Service Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=oil_change_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-tire-shop-receipt')
    def generate_tire_shop_receipt():
        """Pre-configured tire shop receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load tire shop template from JSON file
        tire_shop_config = load_template_config('tire_shop')
        if not tire_shop_config:
            return "Tire Shop template not found", 404
        
        template_name = tire_shop_config.get('name', 'Tire Shop Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=tire_shop_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-stockx-receipt')
    def generate_stockx_receipt():
        """Pre-configured StockX receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load StockX template from JSON file
        stockx_config = load_template_config('stockx')
        if not stockx_config:
            return "StockX template not found", 404
        
        template_name = stockx_config.get('name', 'StockX Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=stockx_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-goat-receipt')
    def generate_goat_receipt():
        """Pre-configured GOAT receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load GOAT template from JSON file
        goat_config = load_template_config('goat')
        if not goat_config:
            return "GOAT template not found", 404
        
        template_name = goat_config.get('name', 'GOAT Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=goat_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-motel6-receipt')
    def generate_motel6_receipt():
        """Pre-configured Motel 6 receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load Motel 6 template from JSON file
        motel6_config = load_template_config('motel6')
        if not motel6_config:
            return "Motel 6 template not found", 404
        
        template_name = motel6_config.get('name', 'Motel 6 Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=motel6_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-rolex-receipt')
    def generate_rolex_receipt():
        """Pre-configured Rolex receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load Rolex template from JSON file
        rolex_config = load_template_config('rolex')
        if not rolex_config:
            return "Rolex template not found", 404
        
        template_name = rolex_config.get('name', 'Rolex Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=rolex_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-dior-receipt')
    def generate_dior_receipt():
        """Pre-configured Dior receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load Dior template from JSON file
        dior_config = load_template_config('dior')
        if not dior_config:
            return "Dior template not found", 404
        
        template_name = dior_config.get('name', 'Dior Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=dior_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-chanel-receipt')
    def generate_chanel_receipt():
        """Pre-configured Chanel receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load Chanel template from JSON file
        chanel_config = load_template_config('chanel')
        if not chanel_config:
            return "Chanel template not found", 404
        
        template_name = chanel_config.get('name', 'Chanel Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=chanel_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-cartier-receipt')
    def generate_cartier_receipt():
        """Pre-configured Cartier receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load Cartier template from JSON file
        cartier_config = load_template_config('cartier')
        if not cartier_config:
            return "Cartier template not found", 404
        
        template_name = cartier_config.get('name', 'Cartier Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=cartier_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-burberry-receipt')
    def generate_burberry_receipt():
        """Pre-configured Burberry receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load Burberry template from JSON file
        burberry_config = load_template_config('burberry')
        if not burberry_config:
            return "Burberry template not found", 404
        
        template_name = burberry_config.get('name', 'Burberry Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=burberry_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-neimanmarcus-receipt')
    def generate_neimanmarcus_receipt():
        """Pre-configured Neiman Marcus receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load Neiman Marcus template from JSON file
        neimanmarcus_config = load_template_config('neimanmarcus')
        if not neimanmarcus_config:
            return "Neiman Marcus template not found", 404
        
        template_name = neimanmarcus_config.get('name', 'Neiman Marcus Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=neimanmarcus_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-pawnshop-receipt')
    def generate_pawnshop_receipt():
        """Pre-configured pawn shop receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load pawn shop template from JSON file
        pawnshop_config = load_template_config('pawnshop')
        if not pawnshop_config:
            return "Pawn Shop template not found", 404
        
        template_name = pawnshop_config.get('name', 'Pawn Shop Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=pawnshop_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-generic-pos-receipt')
    def generate_generic_pos_receipt():
        """Pre-configured generic POS receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load generic POS template from JSON file
        generic_pos_config = load_template_config('generic_pos')
        if not generic_pos_config:
            return "Generic POS template not found", 404
        
        template_name = generic_pos_config.get('name', 'Generic POS Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=generic_pos_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-generic-restaurant-receipt')
    def generate_generic_restaurant_receipt():
        """Pre-configured generic restaurant receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load generic restaurant template from JSON file
        generic_restaurant_config = load_template_config('generic_restaurant')
        if not generic_restaurant_config:
            return "Generic Restaurant template not found", 404
        
        template_name = generic_restaurant_config.get('name', 'Generic Restaurant Bill')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=generic_restaurant_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-generic-hotel-receipt')
    def generate_generic_hotel_receipt():
        """Pre-configured generic hotel receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load generic hotel template from JSON file
        generic_hotel_config = load_template_config('generic_hotel')
        if not generic_hotel_config:
            return "Generic Hotel template not found", 404
        
        template_name = generic_hotel_config.get('name', 'Generic Hotel Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=generic_hotel_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/generate-generic-gas-receipt')
    def generate_generic_gas_receipt():
        """Pre-configured generic gas station receipt template using JSON"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Load generic gas station template from JSON file
        generic_gas_config = load_template_config('generic_gas')
        if not generic_gas_config:
            return "Generic Gas Station template not found", 404
        
        template_name = generic_gas_config.get('name', 'Generic Gas Station Receipt')
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=generic_gas_config,
                             template_name=template_name,
                             is_generator_route=True)
    
    @app.route('/template/starbucks')
    def starbucks_template():
        """Pre-configured Starbucks receipt template"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        # Complete Starbucks receipt configuration - matching real thermal receipt exactly
        starbucks_config = {
            'settings': {
                'currency': '$',
                'selectedFont': 'font-1',
                'textColor': '#000000'
            },
            'header': {
                'logoUrl': 'https://www.starbucks.com/favicon.ico',
                'logoSize': 20,
                'businessName': 'Riverside Retail Park\nPhone: 0161 250 6307\nSTORE # 63225\nVAT No: 273 5224 09',
                'headerAlignment': 'center'
            },
            'customMessages': [
                {
                    'messageText': '---------------------------------------\n---------------------------------------',
                    'messageAlignment': 'left',
                    'messageDivider': '',
                    'showMessageDivider': False
                },
                {
                    'messageText': '1002 Olivias\nddasdsqd\n\nChk 2639',
                    'messageAlignment': 'left',
                    'messageDivider': '---------------------------------------',
                    'showMessageDivider': True
                }
            ],
            'items': [
                {
                    'name': '1 Venti Mocha Latte',
                    'price': '13.90',
                    'quantity': ''
                },
                {
                    'name': 'Oat Milk',
                    'price': '0.50',
                    'quantity': '',
                    'indent': True
                },
                {
                    'name': '1 Chocolate Pie',
                    'price': '3',
                    'quantity': ''
                },
                {
                    'name': '1 Gr Wht Mocha',
                    'price': '11.50',
                    'quantity': ''
                },
                {
                    'name': 'Oat Milk',
                    'price': '0.50',
                    'quantity': '',
                    'indent': True
                }
            ],
            'payment': {
                'taxRate': '9.47',
                'paymentMethod': '',
                'amountPaid': '',
                'cardLastFour': '',
                'subtotal': '29.40',
                'tax': '2.78',
                'total': '32.18'
            },
            'customMessages2': [
                {
                    'messageText': '5/25/2025, 3:48:03 PM',
                    'messageAlignment': 'center',
                    'messageDivider': '---------------------------------------',
                    'showMessageDivider': True
                },
                {
                    'messageText': '03607017',
                    'messageAlignment': 'center',
                    'messageDivider': '',
                    'showMessageDivider': False
                },
                {
                    'messageText': 'Thank you for visiting Starbucks',
                    'messageAlignment': 'center',
                    'messageDivider': '=======================================',
                    'showMessageDivider': True
                }
            ],
            'barcode': {
                'barcodeEnabled': True,
                'barcodeSize': 40,
                'barcodeLength': 100,
                'barcodeDivider': '',
                'showBarcodeDivider': False
            }
        }
        
        return render_template('generate_advanced_v2.html', 
                             has_subscription=has_subscription, 
                             template_config=starbucks_config)
    
    @app.route('/generate-v1')
    def generate_v1():
        """Legacy receipt generator (V1) with fixed section order"""
        try:
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
        except:
            has_subscription = False
        
        return render_template('generate_advanced.html', has_subscription=has_subscription)
    
    @app.route('/generate')
    @app.route('/generate/')
    def generate_redirect():
        """Redirect old /generate URLs to /generate-advanced"""
        return redirect(url_for('generate_advanced'), code=301)
    
    @app.route('/generate/<slug>')
    def generate_template_redirect(slug):
        """Redirect old /generate/[template] URLs to /generate-advanced?template=[template]"""
        # Try to find the template to ensure it exists
        template = get_template_by_slug(slug)
        if template:
            return redirect(url_for('generate_advanced', template=slug), code=301)
        else:
            # If template doesn't exist, redirect to template gallery
            return redirect(url_for('templates_page'), code=301)

    @app.route('/api/add-item', methods=['POST'])
    def add_item():
        return render_template('partials/receipt_item.html', 
                             item_index=request.form.get('index', 0))
    
    def log_receipt_generation(template_type, store_name, content_hash):
        """Log receipt generation for fraud detection and monitoring"""
        from models import ReceiptLog
        import hashlib
        
        try:
            user_id = current_user.id if current_user and current_user.is_authenticated else None
            ip_address = request.remote_addr or request.headers.get('X-Forwarded-For', 'unknown')
            user_agent = request.headers.get('User-Agent', '')
            
            # Check for suspicious patterns
            suspicion_reason = None
            is_suspicious = False
            
            # Check for high volume (>10 receipts in last hour)
            hour_ago = datetime.now() - timedelta(hours=1)
            recent_count = ReceiptLog.query.filter(
                ReceiptLog.user_id == user_id,
                ReceiptLog.created_at > hour_ago
            ).count() if user_id else 0
            
            if recent_count > 10:
                is_suspicious = True
                suspicion_reason = 'high_volume'
            
            # Check for duplicate receipts (same content within 5 minutes)
            five_min_ago = datetime.now() - timedelta(minutes=5)
            duplicate = ReceiptLog.query.filter(
                ReceiptLog.user_id == user_id,
                ReceiptLog.content_hash == content_hash,
                ReceiptLog.created_at > five_min_ago
            ).first() if user_id else None
            
            if duplicate:
                is_suspicious = True
                suspicion_reason = 'duplicate'
            
            # Check for fraud patterns (multiple templates in short time)
            if not is_suspicious and user_id:
                templates_last_min = ReceiptLog.query.filter(
                    ReceiptLog.user_id == user_id,
                    ReceiptLog.created_at > datetime.now() - timedelta(minutes=1)
                ).count()
                if templates_last_min > 5:
                    is_suspicious = True
                    suspicion_reason = 'fraud_pattern'
            
            # Create log entry
            log = ReceiptLog(
                user_id=user_id,
                template_type=template_type,
                store_name=store_name,
                ip_address=ip_address,
                user_agent=user_agent,
                content_hash=content_hash,
                is_suspicious=is_suspicious,
                suspicion_reason=suspicion_reason
            )
            
            db.session.add(log)
            db.session.commit()
            
            if is_suspicious:
                logging.warning(f"🚨 SUSPICIOUS: {suspicion_reason} - User: {user_id}, IP: {ip_address}, Template: {template_type}")
            
            return log
        except Exception as e:
            logging.error(f"Error logging receipt: {str(e)}")
            return None
    
    @app.route('/api/apply-watermark', methods=['POST'])
    def apply_watermark():
        """Apply hard-to-remove watermark using Ghostscript for non-subscribers"""
        import subprocess
        import tempfile
        import hashlib
        import os
        
        try:
            # Get the PDF from the request
            if 'pdf' not in request.files:
                return jsonify({'error': 'No PDF provided'}), 400
            
            pdf_file = request.files['pdf']
            if not pdf_file:
                return jsonify({'error': 'Empty PDF'}), 400
            
            # Extract receipt metadata from form
            template_type = request.form.get('template_type', 'unknown')
            store_name = request.form.get('store_name', '')
            
            # Read original PDF content
            pdf_content = pdf_file.read()
            content_hash = hashlib.sha256(pdf_content).hexdigest()[:16]
            
            # Log the receipt generation
            log_receipt_generation(template_type, store_name, content_hash)
            
            # Check if user has active subscription - skip watermark for paid users
            has_subscription = False
            if current_user and current_user.is_authenticated:
                has_subscription = current_user.has_active_subscription()
            
            if has_subscription:
                # Paid user - return clean PDF
                logging.info(f"✅ Clean receipt (subscriber) - {template_type}")
                return Response(
                    pdf_content,
                    mimetype='application/pdf',
                    headers={'Content-Disposition': 'attachment;filename=receipt.pdf'}
                )
            
            # Non-subscriber - apply Ghostscript watermark that's hard to remove
            try:
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as input_tmp:
                    input_tmp.write(pdf_content)
                    input_path = input_tmp.name
                
                output_path = input_path.replace('.pdf', '_wm.pdf')
                
                # Create PostScript watermark file - embedded in content stream
                watermark_ps = '''
/watermarkText { (ReceiptMake) } def
/watermarkFont { /Helvetica-Bold 14 selectfont } def
/watermarkColor { .75 setgray } def
/watermarkAngle { -35 } def

/pageWidth { currentpagedevice /PageSize get 0 get } def
/pageHeight { currentpagedevice /PageSize get 1 get } def

<< 
  /EndPage { 
    2 eq { pop false } { 
      gsave
      watermarkFont
      watermarkColor
      
      % Draw watermarks across entire page - increased grid
      0 1 15 {
        /row exch def
        0 1 4 {
          /col exch def
          gsave
          col 65 mul 15 add row 45 mul 10 add translate
          watermarkAngle rotate
          0 0 moveto
          watermarkText show
          grestore
        } for
      } for
      
      grestore
      true
    } ifelse
  } bind
>> setpagedevice
'''
                
                watermark_path = input_path.replace('.pdf', '.ps')
                with open(watermark_path, 'w') as f:
                    f.write(watermark_ps)
                
                # Apply watermark with Ghostscript - flattens into content stream
                gs_cmd = [
                    'gs',
                    '-dSAFER',
                    '-dBATCH',
                    '-dNOPAUSE',
                    '-sDEVICE=pdfwrite',
                    '-dCompatibilityLevel=1.7',
                    '-dPDFSETTINGS=/prepress',
                    '-dAutoRotatePages=/None',
                    f'-sOutputFile={output_path}',
                    watermark_path,
                    input_path
                ]
                
                result = subprocess.run(gs_cmd, capture_output=True, timeout=30)
                
                if result.returncode != 0:
                    logging.error(f"Ghostscript error: {result.stderr.decode()}")
                    # Fall back to returning original PDF
                    return Response(
                        pdf_content,
                        mimetype='application/pdf',
                        headers={'Content-Disposition': 'attachment;filename=receipt.pdf'}
                    )
                
                # Read watermarked PDF
                with open(output_path, 'rb') as f:
                    watermarked_pdf = f.read()
                
                # Clean up temp files
                for path in [input_path, output_path, watermark_path]:
                    try:
                        os.unlink(path)
                    except:
                        pass
                
                logging.info(f"✅ Watermarked receipt - {template_type}")
                return Response(
                    watermarked_pdf,
                    mimetype='application/pdf',
                    headers={'Content-Disposition': 'attachment;filename=receipt.pdf'}
                )
                
            except subprocess.TimeoutExpired:
                logging.error("Ghostscript timeout")
                return Response(
                    pdf_content,
                    mimetype='application/pdf',
                    headers={'Content-Disposition': 'attachment;filename=receipt.pdf'}
                )
            except Exception as gs_error:
                logging.error(f"Ghostscript processing error: {str(gs_error)}")
                return Response(
                    pdf_content,
                    mimetype='application/pdf',
                    headers={'Content-Disposition': 'attachment;filename=receipt.pdf'}
                )
        
        except Exception as e:
            logging.error(f"PDF return error: {str(e)}")
            return jsonify({'error': 'PDF processing failed'}), 500

    @app.route('/sitemap-main.xml')
    def sitemap_main():
        """Sitemap containing only the homepage"""
        sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        sitemap_xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        sitemap_xml += '  <url>\n'
        sitemap_xml += f'    <loc>{request.url_root}</loc>\n'
        sitemap_xml += f'    <lastmod>{datetime.now().strftime("%Y-%m-%d")}</lastmod>\n'
        sitemap_xml += '    <changefreq>weekly</changefreq>\n'
        sitemap_xml += '    <priority>1.0</priority>\n'
        sitemap_xml += '  </url>\n'
        sitemap_xml += '</urlset>'
        return Response(sitemap_xml, mimetype='application/xml')

    @app.route('/sitemap.xml')
    def sitemap():
        pages = []
        
        pages.append({
            'loc': request.url_root,
            'lastmod': datetime.now().strftime('%Y-%m-%d'),
            'changefreq': 'weekly',
            'priority': '1.0'
        })
        
        pages.append({
            'loc': request.url_root + 'templates',
            'lastmod': datetime.now().strftime('%Y-%m-%d'),
            'changefreq': 'weekly',
            'priority': '0.9'
        })
        
        pages.append({
            'loc': request.url_root + 'generate',
            'lastmod': datetime.now().strftime('%Y-%m-%d'),
            'changefreq': 'monthly',
            'priority': '0.9'
        })
        
        for template in TEMPLATES:
            # Exclude Generic POS Receipt from sitemap as requested
            if template['slug'] == 'Generic-POS-Receipt':
                continue
                
            pages.append({
                'loc': request.url_root + f"template/{template['slug']}",
                'lastmod': datetime.now().strftime('%Y-%m-%d'),
                'changefreq': 'monthly',
                'priority': '0.8'
            })

        for route_path, entry in programmatic_route_index.items():
            entry_type = entry.get('entry_type', 'page')
            pages.append({
                'loc': request.url_root.rstrip('/') + route_path,
                'lastmod': entry.get('updated_at') or datetime.now().strftime('%Y-%m-%d'),
                'changefreq': 'weekly',
                'priority': '0.85' if entry_type == 'tool' else '0.8'
            })
        
        sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        sitemap_xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        
        for page in pages:
            sitemap_xml += '  <url>\n'
            sitemap_xml += f'    <loc>{page["loc"]}</loc>\n'
            sitemap_xml += f'    <lastmod>{page["lastmod"]}</lastmod>\n'
            sitemap_xml += f'    <changefreq>{page["changefreq"]}</changefreq>\n'
            sitemap_xml += f'    <priority>{page["priority"]}</priority>\n'
            sitemap_xml += '  </url>\n'
        
        sitemap_xml += '</urlset>'
        
        return Response(sitemap_xml, mimetype='application/xml')

    @app.route('/robots.txt')
    def robots():
        robots_txt = f"""User-agent: *
Allow: /
Sitemap: {request.url_root}sitemap.xml
"""
        return Response(robots_txt, mimetype='text/plain')

    @app.route('/pricing')
    def pricing():
        return render_template('pricing.html')

    @app.route('/programmatic/content')
    def programmatic_content_registry():
        """Ops view for spreadsheet-driven programmatic content."""
        entries = sorted(
            programmatic_route_index.values(),
            key=lambda item: item.get('route_path', ''),
        )
        return render_template(
            'programmatic_index.html',
            entries=entries,
            manifest=programmatic_manifest,
        )
    
    @app.route('/terms')
    def terms():
        return render_template('terms.html')
    
    @app.route('/admin/dashboard')
    def admin_dashboard():
        """Admin-only dashboard for receipt generation monitoring and fraud detection"""
        from models import ReceiptLog
        import logging
        
        # Require admin authentication
        if not current_user.is_authenticated:
            return redirect(url_for('index'))  # TODO: Redirect to proper login page
        
        admin_user_id = os.environ.get('ADMIN_USER_ID', 'NONE')
        if current_user.id != admin_user_id:
            return "Unauthorized - Admin access required", 403
        
        try:
            # Get stats
            total_logs = ReceiptLog.query.count()
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_logs = ReceiptLog.query.filter(ReceiptLog.created_at >= today_start).count()
            suspicious_count = ReceiptLog.query.filter_by(is_suspicious=True).count()
            
            # Get unique users
            unique_users = db.session.query(ReceiptLog.user_id).filter(
                ReceiptLog.user_id != None
            ).distinct().count()
            
            # Get recent suspicious logs (last 100)
            suspicious_logs = ReceiptLog.query.filter_by(
                is_suspicious=True
            ).order_by(ReceiptLog.created_at.desc()).limit(50).all()
            
            # Get recent activity (last 100)
            recent_logs = ReceiptLog.query.order_by(
                ReceiptLog.created_at.desc()
            ).limit(100).all()
            
            logging.info(f"Admin dashboard accessed by {current_user.id}")
            
            return render_template('admin_dashboard.html',
                total_logs=total_logs,
                today_logs=today_logs,
                suspicious_count=suspicious_count,
                unique_users=unique_users,
                suspicious_logs=suspicious_logs,
                recent_logs=recent_logs
            )
        
        except Exception as e:
            logging.error(f"Error loading admin dashboard: {str(e)}")
            return f"Error loading dashboard: {str(e)}", 500
    
    def is_admin_user():
        """Check if current user is an admin - restrict to SITE owner only"""
        # Only allow access via environment variable for security
        # Set ADMIN_USER_ID in secrets to your user ID to grant access
        admin_user_id = os.environ.get('ADMIN_USER_ID', 'NONE')
        return current_user.is_authenticated and current_user.id == admin_user_id
    
    def generate_csrf_token():
        """Generate CSRF token for admin actions"""
        import secrets
        if 'csrf_token' not in flask_session:
            flask_session['csrf_token'] = secrets.token_urlsafe(32)
        return flask_session['csrf_token']
    
    def verify_csrf_token(token):
        """Verify CSRF token"""
        return token and flask_session.get('csrf_token') == token
    
    @app.route('/admin/webhook-config')
    def admin_webhook_config():
        """Secure admin endpoint to view/rotate site-wide webhook configuration - ADMIN ONLY"""
        from models import IncomingWebhookConfig
        from flask import jsonify
        
        # Require admin authentication
        if not current_user.is_authenticated:
            return redirect(url_for('index'))  # TODO: Redirect to proper login page
        
        if not is_admin_user():
            return "Unauthorized - Admin access required", 403
        
        try:
            # Get the site-wide webhook config
            site_webhook = IncomingWebhookConfig.query.filter_by(public_id='site-outrank-webhook').first()
            
            if not site_webhook:
                return jsonify({'error': 'Site webhook not configured yet'}), 404
            
            # Get the domain from request
            domain = request.host_url.rstrip('/')
            
            return render_template('admin_webhook_config.html',
                                 webhook_url=f"{domain}/api/incoming/webhooks/site-outrank-webhook",
                                 api_key_hint=site_webhook.api_key_hint,
                                 is_active=site_webhook.is_active,
                                 created_at=site_webhook.created_at,
                                 last_rotated=site_webhook.last_rotated_at,
                                 csrf_token=generate_csrf_token())
        except Exception as e:
            logging.error(f"Error fetching webhook config: {str(e)}")
            return jsonify({'error': 'Failed to fetch webhook configuration'}), 500
    
    @app.route('/admin/outrank-webhook', methods=['GET', 'POST'])
    def admin_outrank_webhook():
        """View and manage Outrank webhook configuration"""
        from models import IncomingWebhookConfig
        from flask import jsonify
        import secrets
        import hashlib
        
        # Require admin authentication (or simple password for now)
        admin_key = request.args.get('key')
        if request.is_json:
            admin_key = admin_key or request.json.get('key')
        admin_password = os.environ.get('ADMIN_PASSWORD', '')
        
        # Allow if admin password is set and matches, or if user is authenticated admin
        has_admin_access = (admin_password and admin_key == admin_password) or (current_user.is_authenticated and is_admin_user())
        
        if not has_admin_access:
            return jsonify({'error': 'Unauthorized - provide ?key=ADMIN_PASSWORD or set ADMIN_PASSWORD env var'}), 401
        
        try:
            outrank_webhook = IncomingWebhookConfig.query.filter_by(public_id='3009a3c0-481d-424a-8ac0-f7306f363179').first()
            
            if not outrank_webhook:
                return jsonify({'error': 'Outrank webhook not configured'}), 404
            
            # GET request - show configuration
            if request.method == 'GET':
                domain = request.host_url.rstrip('/')
                return jsonify({
                    'webhook_url': f"{domain}/api/incoming/webhooks/{outrank_webhook.public_id}",
                    'public_id': outrank_webhook.public_id,
                    'api_key_hint': outrank_webhook.api_key_hint,
                    'is_active': outrank_webhook.is_active,
                    'created_at': outrank_webhook.created_at.isoformat(),
                    'message': 'Use this webhook URL and API key in your Outrank dashboard'
                })
            
            # POST request - rotate API key
            if request.method == 'POST':
                # Generate new API key
                new_api_key = IncomingWebhookConfig.generate_api_key()
                outrank_webhook.api_key_hash = IncomingWebhookConfig.hash_api_key(new_api_key)
                outrank_webhook.api_key_hint = new_api_key[:8]
                outrank_webhook.last_rotated_at = datetime.now()
                
                db.session.commit()
                
                logging.info(f"Outrank webhook API key rotated")
                
                domain = request.host_url.rstrip('/')
                return jsonify({
                    'success': True,
                    'webhook_url': f"{domain}/api/incoming/webhooks/{outrank_webhook.public_id}",
                    'api_key': new_api_key,
                    'api_key_hint': new_api_key[:8],
                    'message': '⚠️ Save this API key - it will not be shown again! Copy it to your Outrank webhook configuration.'
                })
            
        except Exception as e:
            logging.error(f"Error managing Outrank webhook: {str(e)}")
            db.session.rollback()
            return jsonify({'error': f'Error: {str(e)}'}), 500
    
    @app.route('/admin/webhook-config/rotate', methods=['POST'])
    def admin_rotate_webhook_key():
        """Rotate the site-wide webhook API key - ADMIN ONLY"""
        from models import IncomingWebhookConfig
        from flask import jsonify
        import secrets
        import hashlib
        
        # Require admin authentication
        if not current_user.is_authenticated:
            return jsonify({'error': 'Unauthorized - Authentication required'}), 401
        
        if not is_admin_user():
            return jsonify({'error': 'Forbidden - Admin access required'}), 403
        
        # Verify CSRF token
        csrf_token = request.json.get('csrf_token') if request.is_json else request.form.get('csrf_token')
        if not verify_csrf_token(csrf_token):
            logging.warning(f"CSRF token validation failed for user {current_user.id}")
            return jsonify({'error': 'Invalid CSRF token'}), 403
        
        try:
            site_webhook = IncomingWebhookConfig.query.filter_by(public_id='site-outrank-webhook').first()
            
            if not site_webhook:
                return jsonify({'error': 'Site webhook not found'}), 404
            
            # Generate new API key
            new_api_key = secrets.token_urlsafe(32)
            site_webhook.api_key_hash = hashlib.sha256(new_api_key.encode()).hexdigest()
            site_webhook.api_key_hint = new_api_key[-4:]
            site_webhook.last_rotated_at = datetime.now()
            
            db.session.commit()
            
            logging.info(f"Site webhook API key rotated by user {current_user.id}")
            
            # Return the new API key ONCE - user must save it
            return jsonify({
                'success': True,
                'api_key': new_api_key,
                'api_key_hint': new_api_key[-4:],
                'message': 'API key rotated successfully. Save this key - it will not be shown again!'
            })
            
        except Exception as e:
            logging.error(f"Error rotating webhook key: {str(e)}")
            db.session.rollback()
            return jsonify({'error': 'Failed to rotate API key'}), 500

    @app.route('/create-checkout-session', methods=['GET', 'POST'])
    def create_checkout_session():
        from models import Subscription
        
        # Get plan type from form (POST) or None for GET
        plan_type = request.form.get('plan_type') if request.method == 'POST' else None
        
        # NOTE: Pending receipts are now stored via /api/store-pending-receipt
        # They're already in flask_session when user arrives here
        # No need to parse from form data anymore
        
        # Check if user is logged in
        if not current_user.is_authenticated:
            # Store the plan type in session so we can resume after login
            flask_session['pending_checkout_plan'] = plan_type
            flask_session['next_url'] = url_for('create_checkout_session')
            return redirect(url_for('index'))  # TODO: Redirect to proper login page
        
        # Check if Stripe is configured
        if not stripe.api_key or not stripe.api_key.startswith('sk_'):
            logging.error(f"Invalid Stripe key format. Key starts with: {stripe.api_key[:10] if stripe.api_key else 'NONE'}")
            return "Stripe configuration error. Please check your API keys.", 500
        
        # Debug logging
        logging.info(f"Stripe key prefix: {stripe.api_key[:15] if len(stripe.api_key) >= 15 else 'NO KEY'}...")
        
        # Get plan_type from form or session (if resuming after login)
        if not plan_type:
            plan_type = flask_session.pop('pending_checkout_plan', None)
        
        if not plan_type:
            return redirect(url_for('pricing'))
        
        # Define pricing (in cents)
        # Lifetime is a one-time payment, others are subscriptions
        prices = {
            'lifetime': {'amount': 2500, 'type': 'one_time'},
            'weekly': {'amount': 450, 'interval': 'week', 'type': 'subscription'},
            'monthly': {'amount': 900, 'interval': 'month', 'type': 'subscription'},
            'yearly': {'amount': 4700, 'interval': 'year', 'type': 'subscription'}
        }
        
        if plan_type not in prices:
            return "Invalid plan", 400
        
        # Get domain for redirect URLs - use the domain the user is currently on
        # This ensures redirects work for both custom domain and any hosting platform
        domain = request.host
        
        if not domain:
            logging.error("No domain found for Stripe redirect")
            return "Configuration error: No domain available. Please contact support.", 500
        
        logging.info(f"Creating Stripe checkout for user {current_user.id}, plan: {plan_type}, domain: {domain}")
        
        try:
            plan_info = prices[plan_type]
            
            # Build line item based on plan type
            if plan_info['type'] == 'one_time':
                # Lifetime - one-time payment
                line_item = {
                    'price_data': {
                        'currency': 'usd',
                        'unit_amount': plan_info['amount'],
                        'product_data': {
                            'name': 'ReceiptMake Lifetime Access',
                            'description': 'Unlimited watermark-free receipts - forever'
                        }
                    },
                    'quantity': 1,
                }
                checkout_mode = 'payment'
            else:
                # Subscription plans
                line_item = {
                    'price_data': {
                        'currency': 'usd',
                        'unit_amount': plan_info['amount'],
                        'recurring': {
                            'interval': plan_info['interval']
                        },
                        'product_data': {
                            'name': f'ReceiptMake {plan_type.capitalize()} Plan',
                            'description': 'Unlimited watermark-free receipts'
                        }
                    },
                    'quantity': 1,
                }
                checkout_mode = 'subscription'
            
            # Create Stripe checkout session
            checkout_session = stripe.checkout.Session.create(
                customer_email=current_user.email,
                line_items=[line_item],
                mode=checkout_mode,
                success_url=f'https://{domain}/payment-success?session_id={{CHECKOUT_SESSION_ID}}',
                cancel_url=f'https://{domain}/pricing',
                client_reference_id=str(current_user.id),
                metadata={
                    'user_id': str(current_user.id),
                    'plan_type': plan_type,
                    'datafast_visitor_id': request.cookies.get('datafast_visitor_id'),
                    'datafast_session_id': request.cookies.get('datafast_session_id')
                }
            )
            logging.info(f"Stripe checkout session created: {checkout_session.id}")
        
        except Exception as e:
            logging.error(f"Stripe error: {str(e)}")
            return str(e), 500
        
        # Redirect to Stripe checkout
        if checkout_session.url:
            return redirect(checkout_session.url, code=303)
        else:
            logging.error("No checkout URL returned from Stripe")
            return "Payment processing error", 500

    @app.route('/claim-welcome-offer', methods=['POST'])
    def claim_welcome_offer():
        """Special checkout for 24-hour welcome offer at $6/month (50% off)"""
        from models import Subscription
        
        # Check if user is logged in
        if not current_user.is_authenticated:
            flask_session['next_url'] = url_for('dashboard')
            return redirect(url_for('index'))  # TODO: Redirect to proper login page
        
        # SECURITY: Validate the welcome offer is still valid
        if not current_user.is_welcome_offer_valid():
            logging.warning(f"User {current_user.id} attempted to claim expired welcome offer")
            return redirect(url_for('pricing'))
        
        # Check if Stripe is configured
        if not stripe.api_key or not stripe.api_key.startswith('sk_'):
            logging.error("Invalid Stripe key format for welcome offer")
            return "Stripe configuration error. Please check your API keys.", 500
        
        # Get domain for redirect URLs
        domain = request.host
        if not domain:
            logging.error("No domain found for Stripe redirect")
            return "Configuration error: No domain available.", 500
        
        logging.info(f"Creating welcome offer checkout for user {current_user.id}, domain: {domain}")
        
        try:
            # Create Stripe checkout session for $6/month (600 cents)
            # Use ui_mode='embedded' for embedded checkout as fallback
            checkout_session = stripe.checkout.Session.create(
                customer_email=current_user.email,
                line_items=[
                    {
                        'price_data': {
                            'currency': 'usd',
                            'unit_amount': 600,  # $6.00 in cents
                            'recurring': {
                                'interval': 'month'
                            },
                            'product_data': {
                                'name': 'ReceiptMake Premium (New Member VIP Access)',
                                'description': '50% OFF FIRST MONTH - Unlimited watermark-free receipts, professional templates, and HD downloads. Renews at $9/mo.'
                            }
                        },
                        'quantity': 1,
                    },
                ],
                mode='subscription',
                success_url=f'https://{domain}/payment-success?session_id={{CHECKOUT_SESSION_ID}}',
                cancel_url=f'https://{domain}/dashboard',
                client_reference_id=str(current_user.id),
                metadata={
                    'user_id': str(current_user.id),
                    'plan_type': 'monthly_welcome',
                    'is_welcome_offer': 'true',
                    'datafast_visitor_id': request.cookies.get('datafast_visitor_id'),
                    'datafast_session_id': request.cookies.get('datafast_session_id')
                },
                ui_mode='hosted'
            )
            logging.info(f"Welcome offer checkout session created: {checkout_session.id}")
            
            # NOTE: Do NOT consume the offer here - wait until payment is successful
            # The offer will be consumed in the Stripe webhook handler after payment confirmation
            
        except Exception as e:
            logging.error(f"Stripe error for welcome offer: {str(e)}")
            return str(e), 500
        
        # Redirect to Stripe checkout
        if checkout_session.url:
            return redirect(checkout_session.url, code=303)
        else:
            logging.error("No checkout URL returned from Stripe for welcome offer")
            return "Payment processing error", 500

    @app.route('/api/welcome-offer/popup-seen', methods=['POST'])
    def mark_welcome_popup_seen():
        """Mark the welcome offer popup as seen for the current user"""
        if not current_user.is_authenticated:
            return jsonify({'error': 'Not authenticated'}), 401
        
        try:
            current_user.welcome_offer_popup_seen = True
            db.session.commit()
            logging.info(f"Welcome offer popup marked as seen for user {current_user.id}")
            return jsonify({'success': True})
        except Exception as e:
            logging.error(f"Error marking popup seen: {str(e)}")
            db.session.rollback()
            return jsonify({'error': 'Failed to update'}), 500

    @app.route('/payment-success')
    def payment_success():
        from models import Subscription
        
        if not current_user.is_authenticated:
            logging.warning("Payment success accessed by unauthenticated user")
            return redirect(url_for('index'))
        
        session_id = request.args.get('session_id')
        logging.info(f"Payment success page accessed by user {current_user.id}, session_id: {session_id}")
        
        if session_id:
            try:
                # Retrieve the session
                checkout_session = stripe.checkout.Session.retrieve(session_id)
                logging.info(f"Retrieved Stripe session: {session_id}, payment_status: {checkout_session.payment_status}, subscription: {checkout_session.subscription}")
                
                # SECURITY: Verify payment was actually completed
                if checkout_session.payment_status != 'paid':
                    logging.warning(f"Payment not completed for session {session_id}. Status: {checkout_session.payment_status}")
                    return redirect(url_for('pricing'))
                
                # SECURITY: Verify session belongs to current user
                metadata = checkout_session.metadata or {}
                session_user_id = metadata.get('user_id')
                if session_user_id != str(current_user.id):
                    logging.warning(f"Session {session_id} user mismatch. Expected: {current_user.id}, Got: {session_user_id}")
                    return redirect(url_for('pricing'))
                
                # Create subscription record
                plan_type = metadata.get('plan_type', 'monthly')
                is_welcome_offer = metadata.get('is_welcome_offer') == 'true'
                
                # Determine expiration date
                from datetime import datetime, timedelta
                expires_at = datetime.now()
                if plan_type == 'weekly':
                    expires_at += timedelta(weeks=1)
                elif plan_type == 'monthly' or plan_type == 'monthly_welcome':
                    expires_at += timedelta(days=30)
                elif plan_type == 'yearly':
                    expires_at += timedelta(days=365)
                elif plan_type == 'lifetime':
                    expires_at = datetime.now() + timedelta(days=36500) # 100 years
                
                # For lifetime (one-time payments), use payment_intent; for subscriptions, use subscription
                stripe_id = checkout_session.subscription or checkout_session.payment_intent
                
                # Calculate expiry
                expires_at = None
                if plan_type == 'lifetime':
                    # Lifetime access - set expiry far in the future (100 years)
                    expires_at = datetime.now() + timedelta(days=36500)
                elif plan_type == 'weekly':
                    expires_at = datetime.now() + timedelta(weeks=1)
                elif plan_type in ['monthly', 'monthly_welcome']:
                    expires_at = datetime.now() + timedelta(days=30)
                elif plan_type == 'yearly':
                    expires_at = datetime.now() + timedelta(days=365)
                
                # Consume welcome offer if this was a welcome offer purchase
                if is_welcome_offer:
                    current_user.welcome_offer_expires_at = datetime.now()
                    logging.info(f"Welcome offer consumed for user {current_user.id}")
                
                # SECURITY: Ensure we have a valid Stripe ID
                if not stripe_id:
                    logging.error(f"No stripe_id found for session {session_id}")
                    return "Payment processing error - no transaction ID", 500
                
                # SECURITY: Check if this session was already processed
                existing_sub = Subscription.query.filter_by(
                    stripe_subscription_id=stripe_id
                ).first()
                if existing_sub:
                    logging.info(f"Session {session_id} already processed, redirecting to dashboard")
                    return redirect(url_for('dashboard'))
                
                # Always create a new subscription (don't update existing)
                # Cancel any old active subscriptions first
                old_subs = Subscription.query.filter_by(user_id=current_user.id, status='active').all()
                for old_sub in old_subs:
                    logging.info(f"Marking old subscription {old_sub.id} as replaced")
                    old_sub.status = 'replaced'
                
                # Create new subscription
                subscription = Subscription(
                    user_id=current_user.id,
                    stripe_customer_id=checkout_session.customer,
                    stripe_subscription_id=stripe_id,
                    plan_type=plan_type,
                    status='active',
                    expires_at=expires_at
                )
                db.session.add(subscription)
                db.session.commit()
                logging.info(f"Created new subscription {subscription.id} for user {current_user.id}, plan: {plan_type}")
                
                # Check for pending receipt to auto-save (from Remove Watermark flow)
                pending_receipt = flask_session.get('pending_template_save')
                if pending_receipt and isinstance(pending_receipt, dict):
                    try:
                        from models import SavedTemplate
                        import json
                        
                        # SECURITY: Validate session ID matches (prevent cross-session injection)
                        current_session_id = flask_session.get('_id')
                        receipt_session_id = pending_receipt.get('session_id')
                        if not current_session_id or not receipt_session_id or current_session_id != receipt_session_id:
                            logging.warning(f"Session ID mismatch - possible cross-session attack. Current: {current_session_id}, Receipt: {receipt_session_id}")
                            flask_session.pop('pending_template_save', None)
                            raise Exception("Session ID mismatch")
                        
                        # Validate timestamp (only save if receipt is recent - within 1 hour)
                        timestamp = pending_receipt.get('timestamp')
                        if timestamp:
                            receipt_age = datetime.now().timestamp() * 1000 - timestamp
                            if receipt_age > 3600000:  # 1 hour in milliseconds
                                logging.warning(f"Pending receipt too old ({receipt_age}ms), skipping auto-save")
                                flask_session.pop('pending_template_save', None)
                                raise Exception("Receipt too old")
                        
                        # Extract config - handle both dict and JSON string
                        config = pending_receipt.get('config')
                        if isinstance(config, str):
                            config = json.loads(config)
                        elif not isinstance(config, dict):
                            config = {}
                        
                        # Validate config is not empty
                        if not config:
                            logging.warning("Pending receipt has empty config, skipping auto-save")
                            flask_session.pop('pending_template_save', None)
                            raise Exception("Empty receipt config")
                        
                        # Sanitize name and description (already sanitized in API, but double-check)
                        import bleach
                        name = bleach.clean(str(pending_receipt.get('name', 'Auto-saved Receipt')), tags=[], strip=True)[:100]
                        description = bleach.clean(str(pending_receipt.get('description', 'Auto-saved after removing watermark')), tags=[], strip=True)[:500]
                        
                        # Create the template
                        template = SavedTemplate(
                            user_id=current_user.id,
                            name=name,
                            description=description,
                            template_type='custom',
                            config_json=json.dumps(config)
                        )
                        db.session.add(template)
                        db.session.commit()
                        
                        # Clear the pending receipt from session
                        flask_session.pop('pending_template_save', None)
                        
                        # Set a flag to show success message on dashboard
                        flask_session['show_autosave_success'] = True
                        
                        logging.info(f"✅ Auto-saved pending receipt as template {template.id} for user {current_user.id}")
                    except Exception as e:
                        logging.error(f"❌ Error auto-saving pending receipt: {str(e)}", exc_info=True)
                        # Clear stale pending receipt to prevent future attempts
                        flask_session.pop('pending_template_save', None)
                        # Don't fail the payment flow if template save fails
                else:
                    if not pending_receipt:
                        logging.info("ℹ️ No pending receipt in session - skipping auto-save")
                    else:
                        logging.info(f"ℹ️ Pending receipt is not a dict: {type(pending_receipt)}")
                
            except Exception as e:
                logging.error(f"Error processing payment success: {str(e)}", exc_info=True)
                db.session.rollback()
        
        return redirect(url_for('dashboard'))

    @app.route('/dashboard')
    def dashboard():
        if not current_user.is_authenticated:
            return redirect(url_for('index'))  # TODO: Redirect to proper login page
        
        # Debug logging
        has_sub = current_user.has_active_subscription()
        logging.info(f"Dashboard access by user {current_user.id} ({current_user.email}), has_active_subscription: {has_sub}")
        
        response = make_response(render_template('dashboard.html'))
        
        # Clear the auto-save success flag after displaying it
        flask_session.pop('show_autosave_success', None)
        
        # Prevent caching to ensure fresh subscription status
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    
    @app.route('/blog')
    def blog():
        """Blog listing page - shows all published articles from Outrank"""
        from models import BlogPost
        
        posts = BlogPost.query.filter_by(published=True).order_by(BlogPost.published_at.desc()).all()
        
        return render_template('blog.html', posts=posts)
    
    @app.route('/blog/<slug>')
    def blog_post(slug):
        """Individual blog post page"""
        from models import BlogPost
        
        post = BlogPost.query.filter_by(slug=slug, published=True).first_or_404()
        
        # Get related posts (same tags or recent posts)
        related_posts = []
        if post.tags and len(post.tags) > 0:
            # Find posts with similar tags
            related_posts = BlogPost.query.filter(
                BlogPost.id != post.id,
                BlogPost.published == True
            ).order_by(BlogPost.published_at.desc()).limit(2).all()
        else:
            # Just get recent posts
            related_posts = BlogPost.query.filter(
                BlogPost.id != post.id,
                BlogPost.published == True
            ).order_by(BlogPost.published_at.desc()).limit(2).all()
        
        return render_template('blog_post.html', post=post, related_posts=related_posts)
    
    @app.route('/manage-subscription')
    def manage_subscription():
        if not current_user.is_authenticated:
            return redirect(url_for('index'))  # TODO: Redirect to proper login page
        
        return render_template('manage_subscription.html')
    
    @app.route('/cancel-subscription', methods=['POST'])
    def cancel_subscription():
        from models import Subscription
        
        if not current_user.is_authenticated:
            return redirect(url_for('index'))  # TODO: Redirect to proper login page
        
        # Find active subscription
        subscription = Subscription.query.filter_by(
            user_id=current_user.id,
            status='active'
        ).first()
        
        if subscription:
            try:
                # Cancel subscription at period end in Stripe
                if subscription.stripe_subscription_id:
                    stripe.Subscription.modify(
                        subscription.stripe_subscription_id,
                        cancel_at_period_end=True
                    )
                    logging.info(f"Scheduled cancellation for Stripe subscription: {subscription.stripe_subscription_id}")
                
                # Update database to mark subscription as cancellation scheduled
                subscription.cancel_at_period_end = True
                db.session.commit()
                logging.info(f"Subscription {current_user.id} marked for cancellation at period end")
                
            except Exception as e:
                logging.error(f"Error cancelling subscription: {str(e)}")
                return "Error cancelling subscription. Please try again.", 500
        
        return redirect(url_for('manage_subscription'))
    
    @app.route('/reactivate-subscription', methods=['POST'])
    def reactivate_subscription():
        from models import Subscription
        
        if not current_user.is_authenticated:
            return redirect(url_for('index'))  # TODO: Redirect to proper login page
        
        # Find cancelled subscription
        subscription = Subscription.query.filter_by(
            user_id=current_user.id,
            status='active'
        ).first()
        
        if subscription and subscription.cancel_at_period_end:
            try:
                # Reactivate subscription in Stripe
                if subscription.stripe_subscription_id:
                    stripe.Subscription.modify(
                        subscription.stripe_subscription_id,
                        cancel_at_period_end=False
                    )
                    logging.info(f"Reactivated Stripe subscription: {subscription.stripe_subscription_id}")
                
                # Update database to mark subscription as reactivated
                subscription.cancel_at_period_end = False
                db.session.commit()
                logging.info(f"Subscription {current_user.id} reactivated")
                
            except Exception as e:
                logging.error(f"Error reactivating subscription: {str(e)}")
                return "Error reactivating subscription. Please try again.", 500
        
        return redirect(url_for('manage_subscription'))
    
    @app.route('/upgrade-weekly-to-lifetime', methods=['POST'])
    @login_required
    def upgrade_weekly_to_lifetime():
        """Create a checkout session for the $20.50 upgrade from weekly to lifetime"""
        from models import Subscription
        
        # Verify user is eligible for the upgrade
        if not current_user.is_eligible_for_weekly_to_lifetime_upgrade():
            logging.warning(f"User {current_user.id} attempted upgrade but is not eligible")
            return "You are not eligible for this upgrade offer.", 400
        
        # Check if Stripe is configured
        if not stripe.api_key or not stripe.api_key.startswith('sk_'):
            logging.error("Stripe API key not configured for upgrade")
            return "Payment system configuration error. Please contact support.", 500
        
        # Get domain for redirect URLs
        domain = request.host
        if not domain:
            logging.error("No domain found for Stripe redirect")
            return "Configuration error: No domain available.", 500
        
        logging.info(f"Creating upgrade checkout for user {current_user.id}, from weekly to lifetime, domain: {domain}")
        
        try:
            # Create one-time payment checkout session for $20.50
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'unit_amount': 2050,  # $20.50 in cents
                        'product_data': {
                            'name': 'ReceiptMake Lifetime Deal - Upgrade',
                            'description': 'Upgrade from Weekly to Lifetime (credit applied)',
                        },
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=f'https://{domain}/upgrade-success?session_id={{CHECKOUT_SESSION_ID}}',
                cancel_url=f'https://{domain}/dashboard',
                client_reference_id=str(current_user.id),
                customer_email=current_user.email if current_user.email else None,
                metadata={
                    'user_id': str(current_user.id),
                    'upgrade_type': 'weekly_to_lifetime',
                    'plan_type': 'lifetime',
                    'datafast_visitor_id': request.cookies.get('datafast_visitor_id'),
                    'datafast_session_id': request.cookies.get('datafast_session_id')
                }
            )
            
            logging.info(f"Created upgrade checkout session: {checkout_session.id} for user {current_user.id}")
            return redirect(checkout_session.url, code=303)
            
        except stripe.error.StripeError as e:
            logging.error(f"Stripe error creating upgrade checkout: {str(e)}")
            return f"Payment error: {str(e)}", 500
        except Exception as e:
            logging.error(f"Error creating upgrade checkout: {str(e)}")
            return "An error occurred. Please try again.", 500
    
    @app.route('/upgrade-success')
    @login_required
    def upgrade_success():
        """Handle successful upgrade payment"""
        from models import Subscription
        
        session_id = request.args.get('session_id')
        if not session_id:
            return redirect(url_for('dashboard'))
        
        try:
            # Retrieve the checkout session
            checkout_session = stripe.checkout.Session.retrieve(session_id)
            
            # Verify this is an upgrade payment
            if checkout_session.metadata.get('upgrade_type') != 'weekly_to_lifetime':
                return redirect(url_for('dashboard'))
            
            # Verify the user matches
            if checkout_session.metadata.get('user_id') != str(current_user.id):
                logging.warning(f"User mismatch in upgrade success: session user {checkout_session.metadata.get('user_id')} vs current user {current_user.id}")
                return redirect(url_for('dashboard'))
            
            # Check payment status
            if checkout_session.payment_status != 'paid':
                logging.warning(f"Upgrade payment not completed: {session_id}")
                return redirect(url_for('dashboard'))
            
            # Get the user's current weekly subscription
            weekly_sub = current_user.get_active_weekly_subscription()
            
            if weekly_sub:
                try:
                    # Cancel the weekly subscription immediately in Stripe
                    if weekly_sub.stripe_subscription_id:
                        stripe.Subscription.cancel(weekly_sub.stripe_subscription_id)
                        logging.info(f"Cancelled weekly subscription {weekly_sub.stripe_subscription_id} for upgrade")
                    
                    # Update the subscription to lifetime
                    weekly_sub.plan_type = 'lifetime'
                    weekly_sub.status = 'active'
                    weekly_sub.expires_at = None  # Lifetime never expires
                    weekly_sub.stripe_subscription_id = None  # Lifetime has no recurring subscription
                    weekly_sub.cancel_at_period_end = False
                    
                    db.session.commit()
                    logging.info(f"User {current_user.id} upgraded from weekly to lifetime successfully")
                    
                except Exception as e:
                    logging.error(f"Error processing upgrade: {str(e)}")
                    db.session.rollback()
            else:
                # Create a new lifetime subscription if somehow the weekly one is gone
                new_sub = Subscription(
                    user_id=current_user.id,
                    stripe_customer_id=checkout_session.customer,
                    stripe_subscription_id=None,  # Lifetime has no recurring subscription
                    plan_type='lifetime',
                    status='active',
                    expires_at=None
                )
                db.session.add(new_sub)
                db.session.commit()
                logging.info(f"Created new lifetime subscription for user {current_user.id} (upgrade)")
            
            # Store success message in session for display
            flask_session['upgrade_success'] = True
            
            return redirect(url_for('dashboard'))
            
        except stripe.error.StripeError as e:
            logging.error(f"Stripe error in upgrade success: {str(e)}")
            return redirect(url_for('dashboard'))
        except Exception as e:
            logging.error(f"Error in upgrade success: {str(e)}")
            return redirect(url_for('dashboard'))
    
    @app.route('/dismiss-upgrade-offer', methods=['POST'])
    @login_required
    def dismiss_upgrade_offer():
        """Dismiss the upgrade offer (stores in session)"""
        flask_session['upgrade_offer_dismissed'] = True
        return '', 204
    
    @app.route('/webhooks')
    def webhooks():
        from models import WebhookIntegration
        if not current_user.is_authenticated:
            return redirect(url_for('index'))  # TODO: Redirect to proper login page
        
        user_webhooks = WebhookIntegration.query.filter_by(user_id=current_user.id).order_by(WebhookIntegration.created_at.desc()).all()
        return render_template('webhooks.html', webhooks=user_webhooks)
    
    @app.route('/webhooks/create', methods=['POST'])
    def create_webhook():
        from models import WebhookIntegration
        from flask import jsonify
        
        if not current_user.is_authenticated:
            return jsonify({'error': 'Unauthorized'}), 401
        
        try:
            data = request.get_json()
            
            webhook = WebhookIntegration(
                user_id=current_user.id,
                name=data.get('name'),
                endpoint_url=data.get('endpoint_url'),
                access_token=data.get('access_token', '')
            )
            
            db.session.add(webhook)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'webhook': {
                    'id': webhook.id,
                    'name': webhook.name,
                    'endpoint_url': webhook.endpoint_url,
                    'is_active': webhook.is_active,
                    'created_at': webhook.created_at.isoformat()
                }
            })
        except Exception as e:
            logging.error(f"Error creating webhook: {str(e)}")
            return jsonify({'error': 'Failed to create webhook'}), 500
    
    @app.route('/webhooks/<int:webhook_id>/delete', methods=['POST'])
    def delete_webhook(webhook_id):
        from models import WebhookIntegration
        from flask import jsonify
        
        if not current_user.is_authenticated:
            return jsonify({'error': 'Unauthorized'}), 401
        
        webhook = WebhookIntegration.query.filter_by(id=webhook_id, user_id=current_user.id).first()
        
        if not webhook:
            return jsonify({'error': 'Webhook not found'}), 404
        
        db.session.delete(webhook)
        db.session.commit()
        
        return jsonify({'success': True})
    
    @app.route('/webhooks/<int:webhook_id>/toggle', methods=['POST'])
    def toggle_webhook(webhook_id):
        from models import WebhookIntegration
        from flask import jsonify
        
        if not current_user.is_authenticated:
            return jsonify({'error': 'Unauthorized'}), 401
        
        webhook = WebhookIntegration.query.filter_by(id=webhook_id, user_id=current_user.id).first()
        
        if not webhook:
            return jsonify({'error': 'Webhook not found'}), 404
        
        webhook.is_active = not webhook.is_active
        db.session.commit()
        
        return jsonify({'success': True, 'is_active': webhook.is_active})
    
    @app.route('/api/test-webhook', methods=['POST'])
    def test_webhook():
        from flask import jsonify
        import requests
        
        if not current_user.is_authenticated:
            return jsonify({'error': 'Unauthorized'}), 401
        
        try:
            data = request.get_json()
            endpoint_url = data.get('endpoint_url')
            access_token = data.get('access_token', '')
            
            if not endpoint_url:
                return jsonify({'error': 'Endpoint URL is required'}), 400
            
            # Prepare test payload
            headers = {'Content-Type': 'application/json'}
            if access_token:
                headers['Authorization'] = f'Bearer {access_token}'
            
            test_payload = {
                'test': True,
                'message': 'This is a test webhook from ReceiptMake',
                'user_id': current_user.id,
                'user_email': current_user.email,
                'timestamp': datetime.now().isoformat(),
                'sample_receipt_data': {
                    'businessName': 'Test Business',
                    'total': 99.99,
                    'items': [
                        {
                            'quantity': 1,
                            'name': 'Test Item',
                            'price': 99.99
                        }
                    ]
                }
            }
            
            # Send test request
            response = requests.post(
                endpoint_url,
                json=test_payload,
                headers=headers,
                timeout=10
            )
            
            logging.info(f"Test webhook sent to {endpoint_url} - Status: {response.status_code}")
            
            return jsonify({
                'success': True,
                'status_code': response.status_code,
                'response_body': response.text[:200] if response.text else None
            })
            
        except requests.exceptions.Timeout:
            return jsonify({'error': 'Request timed out (>10 seconds)'}), 400
        except requests.exceptions.ConnectionError:
            return jsonify({'error': 'Could not connect to endpoint'}), 400
        except Exception as e:
            logging.error(f"Error testing webhook: {str(e)}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/trigger-webhooks', methods=['POST'])
    def trigger_webhooks():
        from models import WebhookIntegration
        from flask import jsonify
        import requests
        
        if not current_user.is_authenticated:
            return jsonify({'error': 'Unauthorized'}), 401
        
        try:
            receipt_data = request.get_json()
            
            # Get all active webhooks for the user
            webhooks = WebhookIntegration.query.filter_by(
                user_id=current_user.id,
                is_active=True
            ).all()
            
            results = []
            for webhook in webhooks:
                try:
                    headers = {'Content-Type': 'application/json'}
                    if webhook.access_token:
                        headers['Authorization'] = f'Bearer {webhook.access_token}'
                    
                    # Add user info to receipt data
                    payload = {
                        'user_id': current_user.id,
                        'user_email': current_user.email,
                        'receipt_data': receipt_data,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    response = requests.post(
                        webhook.endpoint_url,
                        json=payload,
                        headers=headers,
                        timeout=10
                    )
                    
                    webhook.last_triggered = datetime.now()
                    db.session.commit()
                    
                    results.append({
                        'webhook_id': webhook.id,
                        'webhook_name': webhook.name,
                        'status': 'success',
                        'status_code': response.status_code
                    })
                    
                    logging.info(f"Triggered webhook {webhook.id} ({webhook.name}) - Status: {response.status_code}")
                    
                except Exception as e:
                    logging.error(f"Error triggering webhook {webhook.id}: {str(e)}")
                    results.append({
                        'webhook_id': webhook.id,
                        'webhook_name': webhook.name,
                        'status': 'error',
                        'error': str(e)
                    })
            
            return jsonify({
                'success': True,
                'webhooks_triggered': len(results),
                'results': results
            })
            
        except Exception as e:
            logging.error(f"Error in trigger_webhooks: {str(e)}")
            return jsonify({'error': 'Failed to trigger webhooks'}), 500
    
    # ===========================================
    # USER STATUS - Check authentication status
    # ===========================================
    
    @app.route('/api/user-status')
    def user_status():
        """Check if user is authenticated"""
        from flask import jsonify
        return jsonify({
            'authenticated': current_user.is_authenticated,
            'user_id': current_user.id if current_user.is_authenticated else None
        })
    
    @app.route('/api/retrieve-and-save-pending-receipt', methods=['POST'])
    def retrieve_and_save_pending_receipt():
        """Retrieve a pending receipt from session and save it for authenticated user"""
        from models import SavedTemplate
        from flask import jsonify
        import json
        from datetime import datetime
        
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        try:
            # Get pending receipt from session
            pending_receipt = flask_session.get('pending_template_save')
            if not pending_receipt:
                return jsonify({'success': False, 'error': 'No pending receipt found'}), 404
            
            # SECURITY: Validate session ID matches
            current_session_id = flask_session.get('_id')
            receipt_session_id = pending_receipt.get('session_id')
            if not current_session_id or not receipt_session_id or current_session_id != receipt_session_id:
                logging.warning(f"Session ID mismatch - possible cross-session attack")
                flask_session.pop('pending_template_save', None)
                return jsonify({'success': False, 'error': 'Session mismatch'}), 403
            
            # Validate timestamp (only save if receipt is recent)
            timestamp = pending_receipt.get('timestamp')
            if timestamp:
                receipt_age = datetime.now().timestamp() * 1000 - timestamp
                if receipt_age > 3600000:  # 1 hour
                    logging.warning(f"Pending receipt too old ({receipt_age}ms), rejecting")
                    flask_session.pop('pending_template_save', None)
                    return jsonify({'success': False, 'error': 'Receipt too old'}), 400
            
            # Extract and validate config
            config = pending_receipt.get('config')
            if isinstance(config, str):
                config = json.loads(config)
            elif not isinstance(config, dict):
                config = {}
            
            if not config:
                return jsonify({'success': False, 'error': 'Invalid receipt config'}), 400
            
            # Sanitize name and description
            import bleach
            name = bleach.clean(str(pending_receipt.get('name', 'Saved Receipt')), tags=[], strip=True)[:100]
            description = bleach.clean(str(pending_receipt.get('description', 'Saved from pending receipt')), tags=[], strip=True)[:500]
            
            # Create and save template
            template = SavedTemplate(
                user_id=current_user.id,
                name=name,
                description=description,
                template_type='custom',
                config_json=json.dumps(config)
            )
            db.session.add(template)
            db.session.commit()
            
            # Clear the pending receipt
            flask_session.pop('pending_template_save', None)
            
            logging.info(f"Saved pending receipt as template {template.id} for user {current_user.id}")
            return jsonify({'success': True, 'template_id': template.id})
            
        except Exception as e:
            logging.error(f"Error retrieving and saving pending receipt: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/store-pending-receipt', methods=['POST'])
    def store_pending_receipt():
        """Store a pending receipt server-side for the Remove Watermark flow"""
        from flask import request, jsonify
        from datetime import datetime
        import json
        import secrets
        import hmac
        import hashlib
        
        try:
            data = request.get_json()
            
            # Validate required fields
            if not data or not data.get('config') or not data.get('intent'):
                return jsonify({'success': False, 'error': 'Missing required fields'}), 400
            
            # Only accept remove_watermark intent
            if data.get('intent') != 'remove_watermark':
                return jsonify({'success': False, 'error': 'Invalid intent'}), 400
            
            # Sanitize name and description to prevent XSS
            import bleach
            name = bleach.clean(data.get('name', 'Auto-saved Receipt'), tags=[], strip=True)
            description = bleach.clean(data.get('description', 'Auto-saved after removing watermark'), tags=[], strip=True)
            
            # Generate a secure token to bind this receipt to this session
            token = secrets.token_urlsafe(32)
            
            # Add timestamp server-side (don't trust client timestamp)
            receipt_data = {
                'intent': 'remove_watermark',
                'name': name[:100],  # Limit length
                'description': description[:500],  # Limit length
                'config': data.get('config'),
                'timestamp': datetime.now().timestamp() * 1000,
                'autoSave': True,
                'token': token,  # Bind to this specific session/request
                'session_id': flask_session.get('_id', secrets.token_hex(16))  # Track session
            }
            
            # Store session ID if not already set
            if '_id' not in flask_session:
                flask_session['_id'] = receipt_data['session_id']
            
            # Store in server-side session
            flask_session['pending_template_save'] = receipt_data
            
            logging.info(f"Stored pending receipt in server session with token (session_id: {receipt_data['session_id']})")
            return jsonify({'success': True, 'token': token})
            
        except Exception as e:
            logging.error(f"Error storing pending receipt: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # ===========================================
    # SAVED TEMPLATES - Manage user's saved receipt templates
    # ===========================================
    
    @app.route('/api/templates', methods=['GET'])
    def list_templates():
        """List all saved templates for the current user"""
        from models import SavedTemplate
        from flask import jsonify
        
        if not current_user.is_authenticated:
            return jsonify({'error': 'Unauthorized'}), 401
        
        try:
            templates = SavedTemplate.query.filter_by(
                user_id=current_user.id
            ).order_by(SavedTemplate.updated_at.desc()).all()
            
            templates_data = []
            for template in templates:
                templates_data.append({
                    'id': template.id,
                    'name': template.name,
                    'description': template.description,
                    'template_type': template.template_type,
                    'created_at': template.created_at.isoformat(),
                    'updated_at': template.updated_at.isoformat(),
                    'last_used_at': template.last_used_at.isoformat() if template.last_used_at else None
                })
            
            return jsonify({
                'success': True,
                'templates': templates_data
            })
            
        except Exception as e:
            logging.error(f"Error listing templates: {str(e)}")
            return jsonify({'error': 'Failed to list templates'}), 500
    
    @app.route('/api/templates/<int:template_id>', methods=['GET'])
    def get_template(template_id):
        """Get a specific saved template"""
        from models import SavedTemplate
        from flask import jsonify
        
        if not current_user.is_authenticated:
            return jsonify({'error': 'Unauthorized'}), 401
        
        try:
            template = SavedTemplate.query.filter_by(
                id=template_id,
                user_id=current_user.id
            ).first()
            
            if not template:
                return jsonify({'error': 'Template not found'}), 404
            
            template.last_used_at = datetime.now()
            db.session.commit()
            
            return jsonify({
                'success': True,
                'template': {
                    'id': template.id,
                    'name': template.name,
                    'description': template.description,
                    'template_type': template.template_type,
                    'config_json': template.config_json,
                    'created_at': template.created_at.isoformat(),
                    'updated_at': template.updated_at.isoformat(),
                    'last_used_at': template.last_used_at.isoformat() if template.last_used_at else None
                }
            })
            
        except Exception as e:
            logging.error(f"Error getting template: {str(e)}")
            return jsonify({'error': 'Failed to get template'}), 500
    
    def validate_and_sanitize_template_config(config):
        """Validate and sanitize template configuration to prevent XSS"""
        if not isinstance(config, dict):
            raise ValueError("Configuration must be an object")
        
        if 'sections' not in config or not isinstance(config['sections'], list):
            raise ValueError("Configuration must have a 'sections' array")
        
        allowed_section_types = {'settings', 'header', 'dateTime', 'twoColumn', 'items', 'payment', 'customMessage', 'barcode'}
        allowed_keys_per_type = {
            'settings': {'currencyFormat', 'selectedFont', 'textColor', 'showBackground'},
            'header': {'logoUrl', 'headerAlignment', 'logoSize', 'businessName', 'headerDivider', 'showHeaderDivider'},
            'dateTime': {'dateAlignment', 'dateTime', 'dateDivider', 'showDateDivider'},
            'twoColumn': {'customFields', 'infoDivider', 'showInfoDivider'},
            'items': {'items', 'itemsDivider', 'showItemsDivider'},
            'payment': {'taxRate', 'paymentType', 'paymentFields', 'paymentDivider', 'showPaymentDivider'},
            'customMessage': {'customMessage', 'messageText', 'messageAlignment', 'messageDivider', 'showMessageDivider'},
            'barcode': {'barcodeEnabled', 'barcodeSize', 'barcodeLength', 'barcodeDivider', 'showBarcodeDivider'}
        }
        
        sanitized_sections = []
        for section in config['sections']:
            if not isinstance(section, dict):
                continue
            
            section_type = section.get('type')
            if section_type not in allowed_section_types:
                continue
            
            allowed_keys = allowed_keys_per_type.get(section_type, set())
            section_data = section.get('data', {})
            
            if not isinstance(section_data, dict):
                continue
            
            sanitized_data = {}
            for key in allowed_keys:
                if key in section_data:
                    value = section_data[key]
                    if isinstance(value, str):
                        sanitized_data[key] = value[:1000]
                    elif isinstance(value, (int, float, bool)):
                        sanitized_data[key] = value
                    elif isinstance(value, list):
                        sanitized_data[key] = value[:100]
                    else:
                        sanitized_data[key] = value
            
            sanitized_sections.append({
                'type': section_type,
                'data': sanitized_data,
                'collapsed': bool(section.get('collapsed', False))
            })
        
        return {'sections': sanitized_sections}
    
    @app.route('/api/templates', methods=['POST'])
    def save_template():
        """Save a new template or update existing one"""
        from models import SavedTemplate
        from flask import jsonify
        
        if not current_user.is_authenticated:
            return jsonify({'error': 'Unauthorized'}), 401
        
        try:
            data = request.get_json()
            
            if not data.get('name'):
                return jsonify({'error': 'Template name is required'}), 400
            
            if not data.get('config_json'):
                return jsonify({'error': 'Template configuration is required'}), 400
            
            config_json = data.get('config_json')
            if not isinstance(config_json, dict):
                return jsonify({'error': 'Invalid template configuration format'}), 400
            
            config_json = validate_and_sanitize_template_config(config_json)
            
            config_str = json.dumps(config_json)
            if len(config_str) > 500000:
                return jsonify({'error': 'Template configuration too large (max 500KB)'}), 400
            
            existing_template = SavedTemplate.query.filter_by(
                user_id=current_user.id,
                name=data.get('name')
            ).first()
            
            if existing_template:
                existing_template.description = data.get('description', '')
                existing_template.template_type = data.get('template_type', 'custom')
                existing_template.config_json = config_json
                existing_template.updated_at = datetime.now()
                template = existing_template
                action = 'updated'
            else:
                # Check subscription status for template limits
                has_subscription = current_user.has_active_subscription()
                template_count = SavedTemplate.query.filter_by(user_id=current_user.id).count()
                
                # Free users: max 2 templates
                # Paid users: unlimited
                if not has_subscription and template_count >= 2:
                    return jsonify({'error': 'Free account limited to 2 templates. Upgrade to Premium for unlimited templates.', 'limit': 2, 'current_count': template_count}), 400
                
                template = SavedTemplate(
                    user_id=current_user.id,
                    name=data.get('name'),
                    description=data.get('description', ''),
                    template_type=data.get('template_type', 'custom'),
                    config_json=config_json
                )
                db.session.add(template)
                action = 'created'
            
            db.session.commit()
            
            logging.info(f"Template {action} for user {current_user.id}: {template.name}")
            
            return jsonify({
                'success': True,
                'action': action,
                'template': {
                    'id': template.id,
                    'name': template.name,
                    'description': template.description,
                    'template_type': template.template_type,
                    'created_at': template.created_at.isoformat(),
                    'updated_at': template.updated_at.isoformat()
                }
            })
            
        except Exception as e:
            logging.error(f"Error saving template: {str(e)}")
            db.session.rollback()
            return jsonify({'error': 'Failed to save template'}), 500
    
    @app.route('/api/templates/<int:template_id>', methods=['DELETE'])
    def delete_template(template_id):
        """Delete a saved template"""
        from models import SavedTemplate
        from flask import jsonify
        
        if not current_user.is_authenticated:
            return jsonify({'error': 'Unauthorized'}), 401
        
        try:
            template = SavedTemplate.query.filter_by(
                id=template_id,
                user_id=current_user.id
            ).first()
            
            if not template:
                return jsonify({'error': 'Template not found'}), 404
            
            template_name = template.name
            db.session.delete(template)
            db.session.commit()
            
            logging.info(f"Template deleted for user {current_user.id}: {template_name}")
            
            return jsonify({
                'success': True,
                'message': 'Template deleted successfully'
            })
            
        except Exception as e:
            logging.error(f"Error deleting template: {str(e)}")
            db.session.rollback()
            return jsonify({'error': 'Failed to delete template'}), 500
    
    # ===========================================
    # INCOMING WEBHOOKS - Receive data FROM external services
    # ===========================================
    
    @app.route('/api/incoming/webhooks/<public_id>', methods=['POST', 'GET'])
    def receive_incoming_webhook(public_id):
        """Endpoint for external services to send data TO ReceiptMake"""
        from models import IncomingWebhookConfig, IncomingWebhookEvent, User
        from flask import jsonify
        import hashlib
        
        try:
            # Get the webhook config by public_id
            config = IncomingWebhookConfig.query.filter_by(public_id=public_id).first()
            
            # Auto-create Outrank webhook if it doesn't exist but matches the expected public_id
            if not config and public_id == '3009a3c0-481d-424a-8ac0-f7306f363179':
                logging.info(f"Auto-creating Outrank webhook configuration")
                try:
                    # Ensure OUTRANK user exists
                    outrank_user = User.query.filter_by(id='OUTRANK').first()
                    if not outrank_user:
                        outrank_user = User(
                            id='OUTRANK',
                            email='outrank@receiptmake.com',
                            first_name='Outrank',
                            last_name='Integration'
                        )
                        db.session.add(outrank_user)
                        db.session.commit()
                        logging.info("Created OUTRANK system user")
                    
                    # Create the webhook with hardcoded API key
                    api_key = '2U26PfXMgvdWqwwN7gLHSbFDCC3tHAumAoF-N86lUJs'
                    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
                    api_key_hint = api_key[-4:]
                    
                    config = IncomingWebhookConfig(
                        user_id='OUTRANK',
                        public_id='3009a3c0-481d-424a-8ac0-f7306f363179',
                        api_key_hash=api_key_hash,
                        api_key_hint=api_key_hint,
                        is_active=True
                    )
                    db.session.add(config)
                    db.session.commit()
                    logging.info(f"✅ Outrank webhook auto-created: {public_id}")
                except Exception as e:
                    logging.error(f"Failed to auto-create webhook: {str(e)}")
                    db.session.rollback()
            
            if not config:
                logging.warning(f"Incoming webhook not found: {public_id}")
                return jsonify({'error': 'Webhook not found', 'status': 'invalid_public_id'}), 404
            
            if not config.is_active:
                logging.warning(f"Incoming webhook inactive: {public_id}")
                return jsonify({'error': 'Webhook is inactive', 'status': 'webhook_inactive'}), 403
            
            # For GET requests or empty POST (test requests), return success to verify endpoint exists
            if request.method == 'GET':
                return jsonify({
                    'status': 'active',
                    'message': 'Webhook endpoint is active. Send POST requests with Authorization header.',
                    'webhook_id': public_id
                }), 200
            
            # For POST requests without body (test from Outrank), return 200 to confirm endpoint works
            payload = request.get_json(silent=True)
            if not payload:
                return jsonify({
                    'status': 'ready',
                    'message': 'Webhook endpoint is ready. Send articles with Authorization: Bearer {api_key}',
                    'webhook_id': public_id
                }), 200
            
            # Verify API key from Authorization header for actual data
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                event = IncomingWebhookEvent(
                    config_id=config.id,
                    status='invalid_auth',
                    payload=payload,
                    headers=dict(request.headers),
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent'),
                    error_message='Missing or invalid Authorization header',
                    http_status=401
                )
                db.session.add(event)
                db.session.commit()
                return jsonify({'error': 'Missing Authorization header. Use: Authorization: Bearer YOUR_API_KEY', 'status': 'auth_required'}), 401
            
            api_key = auth_header[7:]  # Remove 'Bearer ' prefix
            
            if not config.verify_api_key(api_key):
                event = IncomingWebhookEvent(
                    config_id=config.id,
                    status='invalid_auth',
                    payload=None,
                    headers=dict(request.headers),
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent'),
                    error_message='Invalid API key',
                    http_status=401
                )
                db.session.add(event)
                db.session.commit()
                logging.warning(f"Invalid API key for incoming webhook: {public_id}")
                return jsonify({'error': 'Invalid API key'}), 401
            
            # Get the payload
            try:
                payload = request.get_json()
            except Exception as e:
                event = IncomingWebhookEvent(
                    config_id=config.id,
                    status='failed',
                    payload=None,
                    headers=dict(request.headers),
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent'),
                    error_message=f'Invalid JSON payload: {str(e)}',
                    http_status=400
                )
                db.session.add(event)
                db.session.commit()
                return jsonify({'error': 'Invalid JSON payload'}), 400
            
            # Log the raw payload for debugging
            logging.info(f"📥 Webhook payload received: {payload}")
            logging.info(f"📋 Webhook headers: {dict(request.headers)}")
            
            # Store the event
            event = IncomingWebhookEvent(
                config_id=config.id,
                status='pending',
                payload=payload,
                headers=dict(request.headers),
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent'),
                http_status=202
            )
            db.session.add(event)
            try:
                db.session.commit()
            except Exception as db_error:
                logging.error(f"Database error storing webhook event: {str(db_error)}")
                db.session.rollback()
                return jsonify({'error': 'Database error'}), 500
            
            logging.info(f"Incoming webhook received successfully: {public_id} - Event ID: {event.id}")
            
            # Process publish_articles events from Outrank
            if payload and payload.get('event_type') == 'publish_articles':
                try:
                    from models import BlogPost
                    from dateutil import parser as date_parser
                    
                    # Validate payload structure
                    if not isinstance(payload.get('data'), dict):
                        raise ValueError("Missing or invalid 'data' field in payload")
                    
                    articles_data = payload.get('data', {}).get('articles', [])
                    if not isinstance(articles_data, list):
                        raise ValueError("'articles' must be a list")
                    
                    logging.info(f"Processing {len(articles_data)} articles from Outrank")
                    
                    created_count = 0
                    updated_count = 0
                    
                    for article_data in articles_data:
                        try:
                            outrank_id = article_data.get('id')
                            if not outrank_id:
                                logging.warning(f"Skipping article without ID: {article_data}")
                                continue
                            
                            # Validate required fields
                            if not article_data.get('title') or not article_data.get('slug'):
                                logging.warning(f"Skipping article {outrank_id}: missing title or slug")
                                continue
                            
                            # Check if article already exists
                            existing_post = BlogPost.query.filter_by(outrank_id=outrank_id).first()
                            
                            # Parse the created_at timestamp
                            published_at = None
                            if article_data.get('created_at'):
                                try:
                                    published_at = date_parser.parse(article_data['created_at'])
                                except Exception as date_error:
                                    logging.warning(f"Could not parse date for article {outrank_id}: {str(date_error)}")
                                    published_at = datetime.now()
                            
                            if existing_post:
                                # Update existing article
                                existing_post.title = article_data.get('title', existing_post.title)
                                existing_post.slug = article_data.get('slug', existing_post.slug)
                                existing_post.content_markdown = article_data.get('content_markdown')
                                existing_post.content_html = article_data.get('content_html')
                                existing_post.meta_description = article_data.get('meta_description')
                                existing_post.image_url = article_data.get('image_url')
                                existing_post.tags = article_data.get('tags', [])
                                existing_post.updated_at = datetime.now()
                                updated_count += 1
                                logging.info(f"✏️ Updated article: {existing_post.title}")
                            else:
                                # Create new article
                                new_post = BlogPost(
                                    outrank_id=outrank_id,
                                    title=article_data.get('title'),
                                    slug=article_data.get('slug'),
                                    content_markdown=article_data.get('content_markdown'),
                                    content_html=article_data.get('content_html'),
                                    meta_description=article_data.get('meta_description'),
                                    image_url=article_data.get('image_url'),
                                    tags=article_data.get('tags', []),
                                    published=True,
                                    published_at=published_at or datetime.now()
                                )
                                db.session.add(new_post)
                                created_count += 1
                                logging.info(f"✨ Created new article: {new_post.title}")
                        
                        except Exception as article_error:
                            logging.error(f"Error processing article {article_data.get('id')}: {str(article_error)}")
                            import traceback
                            logging.error(traceback.format_exc())
                            continue
                    
                    # Commit all blog posts with error handling
                    try:
                        db.session.commit()
                        event.status = 'success'
                        event.processed_at = datetime.now()
                        db.session.commit()
                        logging.info(f"✅ Blog posts processed: {created_count} created, {updated_count} updated")
                    except Exception as commit_error:
                        logging.error(f"Database commit error: {str(commit_error)}")
                        db.session.rollback()
                        event.status = 'failed'
                        event.error_message = f'Database commit failed: {str(commit_error)}'
                        try:
                            db.session.commit()
                        except:
                            pass
                    
                except Exception as processing_error:
                    logging.error(f"❌ Error processing webhook payload: {str(processing_error)}")
                    import traceback
                    logging.error(traceback.format_exc())
                    try:
                        event.status = 'failed'
                        event.error_message = str(processing_error)
                        db.session.commit()
                    except:
                        db.session.rollback()
            
            return jsonify({
                'success': True,
                'message': 'Webhook received successfully',
                'event_id': event.request_id
            }), 202
            
        except Exception as e:
            logging.error(f"Error processing incoming webhook: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            try:
                db.session.rollback()
            except:
                pass
            return jsonify({'error': 'Internal server error', 'details': str(e)}), 500
    
    @app.route('/api/incoming/webhooks/initialize', methods=['POST'])
    def initialize_incoming_webhook():
        """Initialize incoming webhook configuration for a user"""
        from models import IncomingWebhookConfig
        from flask import jsonify
        
        if not current_user.is_authenticated:
            return jsonify({'error': 'Unauthorized'}), 401
        
        try:
            # Check if config already exists
            config = IncomingWebhookConfig.query.filter_by(user_id=current_user.id).first()
            
            if config:
                return jsonify({
                    'success': True,
                    'message': 'Configuration already exists',
                    'public_id': config.public_id,
                    'api_key_hint': config.api_key_hint
                })
            
            # Generate new API key
            api_key = IncomingWebhookConfig.generate_api_key()
            api_key_hash = IncomingWebhookConfig.hash_api_key(api_key)
            api_key_hint = api_key[:8]
            
            # Create new config
            config = IncomingWebhookConfig(
                user_id=current_user.id,
                api_key_hash=api_key_hash,
                api_key_hint=api_key_hint
            )
            db.session.add(config)
            db.session.commit()
            
            # Get the webhook URL
            webhook_url = request.host_url.rstrip('/') + f'/api/incoming/webhooks/{config.public_id}'
            
            logging.info(f"Initialized incoming webhook for user {current_user.id}")
            
            return jsonify({
                'success': True,
                'webhook_url': webhook_url,
                'api_key': api_key,
                'api_key_hint': api_key_hint,
                'public_id': config.public_id
            })
            
        except Exception as e:
            logging.error(f"Error initializing incoming webhook: {str(e)}")
            db.session.rollback()
            return jsonify({'error': 'Failed to initialize webhook'}), 500
    
    @app.route('/api/incoming/webhooks/rotate-key', methods=['POST'])
    def rotate_incoming_webhook_key():
        """Rotate the API key for incoming webhooks"""
        from models import IncomingWebhookConfig
        from flask import jsonify
        
        if not current_user.is_authenticated:
            return jsonify({'error': 'Unauthorized'}), 401
        
        try:
            config = IncomingWebhookConfig.query.filter_by(user_id=current_user.id).first()
            
            if not config:
                return jsonify({'error': 'No webhook configuration found'}), 404
            
            # Generate new API key
            api_key = IncomingWebhookConfig.generate_api_key()
            config.api_key_hash = IncomingWebhookConfig.hash_api_key(api_key)
            config.api_key_hint = api_key[:8]
            config.last_rotated_at = datetime.now()
            
            db.session.commit()
            
            logging.info(f"Rotated API key for user {current_user.id}")
            
            return jsonify({
                'success': True,
                'api_key': api_key,
                'api_key_hint': api_key[:8]
            })
            
        except Exception as e:
            logging.error(f"Error rotating API key: {str(e)}")
            db.session.rollback()
            return jsonify({'error': 'Failed to rotate API key'}), 500
    
    @app.route('/api/incoming/webhooks/toggle', methods=['POST'])
    def toggle_incoming_webhook():
        """Toggle incoming webhook active status"""
        from models import IncomingWebhookConfig
        from flask import jsonify
        
        if not current_user.is_authenticated:
            return jsonify({'error': 'Unauthorized'}), 401
        
        try:
            config = IncomingWebhookConfig.query.filter_by(user_id=current_user.id).first()
            
            if not config:
                return jsonify({'error': 'No webhook configuration found'}), 404
            
            config.is_active = not config.is_active
            db.session.commit()
            
            return jsonify({
                'success': True,
                'is_active': config.is_active
            })
            
        except Exception as e:
            logging.error(f"Error toggling webhook: {str(e)}")
            db.session.rollback()
            return jsonify({'error': 'Failed to toggle webhook'}), 500
    
    @app.route('/api/incoming/webhooks/history', methods=['GET'])
    def get_incoming_webhook_history():
        """Get incoming webhook event history"""
        from models import IncomingWebhookConfig, IncomingWebhookEvent
        from flask import jsonify
        
        if not current_user.is_authenticated:
            return jsonify({'error': 'Unauthorized'}), 401
        
        try:
            config = IncomingWebhookConfig.query.filter_by(user_id=current_user.id).first()
            
            if not config:
                return jsonify({'events': []})
            
            # Get last 50 events
            events = IncomingWebhookEvent.query.filter_by(
                config_id=config.id
            ).order_by(
                IncomingWebhookEvent.received_at.desc()
            ).limit(50).all()
            
            events_data = []
            for event in events:
                events_data.append({
                    'id': event.id,
                    'request_id': event.request_id,
                    'status': event.status,
                    'payload': event.payload,
                    'headers': event.headers,
                    'ip_address': event.ip_address,
                    'user_agent': event.user_agent,
                    'received_at': event.received_at.isoformat() if event.received_at else None,
                    'error_message': event.error_message,
                    'http_status': event.http_status
                })
            
            return jsonify({
                'success': True,
                'events': events_data
            })
            
        except Exception as e:
            logging.error(f"Error getting webhook history: {str(e)}")
            return jsonify({'error': 'Failed to get history'}), 500

    @app.route('/<path:dynamic_path>', methods=['GET'])
    def programmatic_dynamic_page(dynamic_path):
        """Serve generated programmatic pages/tools from manifest entries."""
        normalized_path = '/' + dynamic_path.strip('/')
        if len(normalized_path) > 1 and normalized_path.endswith('/'):
            normalized_path = normalized_path[:-1]

        entry = programmatic_route_index.get(normalized_path)
        if not entry:
            return "Page not found", 404

        return render_template('programmatic_entry.html', entry=entry)
    
    @app.route('/stripe-webhook', methods=['POST'])
    def stripe_webhook():
        from models import Subscription
        from flask import jsonify
        
        payload = request.data
        sig_header = request.headers.get('Stripe-Signature')
        webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
        
        try:
            # Verify webhook signature
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        except ValueError as e:
            logging.error(f"Invalid webhook payload: {str(e)}")
            return jsonify({'error': 'Invalid payload'}), 400
        except Exception as e:
            # Handle signature verification errors
            if 'SignatureVerificationError' in str(type(e).__name__):
                logging.error(f"Invalid webhook signature: {str(e)}")
                return jsonify({'error': 'Invalid signature'}), 400
            raise
        
        # Handle the event
        event_type = event['type']
        event_data = event['data']['object']
        
        logging.info(f"Received Stripe webhook: {event_type}")
        
        try:
            # Subscription updated (renewals, status changes)
            if event_type == 'customer.subscription.updated':
                stripe_sub_id = event_data['id']
                status = event_data['status']
                current_period_end = event_data['current_period_end']
                
                subscription = Subscription.query.filter_by(stripe_subscription_id=stripe_sub_id).first()
                
                if subscription:
                    # Update status
                    if status == 'active':
                        subscription.status = 'active'
                        subscription.expires_at = datetime.fromtimestamp(current_period_end)
                        logging.info(f"Subscription {stripe_sub_id} renewed until {subscription.expires_at}")
                    elif status in ['past_due', 'unpaid', 'canceled']:
                        subscription.status = 'inactive'
                        logging.info(f"Subscription {stripe_sub_id} status changed to {status}")
                    
                    db.session.commit()
            
            # Subscription deleted (cancellation)
            elif event_type == 'customer.subscription.deleted':
                stripe_sub_id = event_data['id']
                
                subscription = Subscription.query.filter_by(stripe_subscription_id=stripe_sub_id).first()
                
                if subscription:
                    subscription.status = 'inactive'
                    db.session.commit()
                    logging.info(f"Subscription {stripe_sub_id} canceled")
            
            # Invoice payment succeeded (renewal payment)
            elif event_type == 'invoice.payment_succeeded':
                stripe_sub_id = event_data.get('subscription')
                billing_reason = event_data.get('billing_reason')
                
                if stripe_sub_id and billing_reason == 'subscription_cycle':
                    subscription = Subscription.query.filter_by(stripe_subscription_id=stripe_sub_id).first()
                    
                    if subscription:
                        # Payment succeeded, ensure subscription is active
                        subscription.status = 'active'
                        
                        # Extend expiry based on plan type
                        if subscription.plan_type == 'weekly':
                            subscription.expires_at = datetime.now() + timedelta(weeks=1)
                        elif subscription.plan_type == 'monthly':
                            subscription.expires_at = datetime.now() + timedelta(days=30)
                        elif subscription.plan_type == 'yearly':
                            subscription.expires_at = datetime.now() + timedelta(days=365)
                        
                        db.session.commit()
                        logging.info(f"Subscription {stripe_sub_id} payment succeeded, extended to {subscription.expires_at}")
            
            # Invoice payment failed
            elif event_type == 'invoice.payment_failed':
                stripe_sub_id = event_data.get('subscription')
                
                if stripe_sub_id:
                    subscription = Subscription.query.filter_by(stripe_subscription_id=stripe_sub_id).first()
                    
                    if subscription:
                        subscription.status = 'past_due'
                        db.session.commit()
                        logging.warning(f"Subscription {stripe_sub_id} payment failed")
            
            else:
                logging.info(f"Unhandled webhook event type: {event_type}")
        
        except Exception as e:
            logging.error(f"Error processing webhook: {str(e)}")
            return jsonify({'error': 'Processing failed'}), 500
        
        return jsonify({'status': 'success'}), 200
    
    return app


# Create app instance
app = create_app()

if __name__ == '__main__':
    app.run(
        host=os.environ.get('HOST', '0.0.0.0'),
        port=int(os.environ.get('PORT', '5000')),
        debug=app.config.get('DEBUG', False),
    )
