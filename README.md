# ReceiptForge - Receipt Generator SaaS Boilerplate

A production-ready Flask SaaS boilerplate for building receipt generation applications. Decoupled from Replit, featuring MakeMyReceipt design system, Stripe subscriptions, and 100+ customizable receipt templates.

![ReceiptForge](https://img.shields.io/badge/Flask-3.0+-blue?logo=flask)
![Tailwind](https://img.shields.io/badge/Tailwind-CSS-38B2AC?logo=tailwind-css)
![Stripe](https://img.shields.io/badge/Stripe-Integrated-635BFF?logo=stripe)
![License](https://img.shields.io/badge/License-MIT-green)

## ✨ Features

### Core Functionality
- 🎨 **100+ Receipt Templates** - Retail, restaurants, services, gas stations, pharmacies
- ⚡ **Live Receipt Generator** - Real-time preview with drag-and-drop builder
- 📄 **PDF Export** - High-quality PDF generation with ReportLab
- 💾 **Save Templates** - User dashboard for saved template management
- 📱 **Fully Responsive** - Works perfectly on mobile, tablet, and desktop

### SaaS Features
- 💳 **Stripe Integration** - Complete subscription management (weekly, monthly, yearly, lifetime)
- 👤 **User Authentication** - Flask-Login ready (Replit Auth removed)
- 📊 **User Dashboard** - Manage subscriptions, saved templates, receipt history
- 🎯 **Landing Pages** - 18+ industry-specific landing pages
- 📝 **Blog System** - Built-in blog with markdown support

### Design System
- 🎨 **MakeMyReceipt Design** - Orange (#FF6B35) color scheme
- ✨ **3D Shadow Effects** - `shadow-[3px_3px_0_0_#000000]` on interactive elements
- 🎯 **Bold Borders** - 2px borders for visual clarity
- 📐 **Responsive Grids** - 2/3/4/5 column layouts
- 🔥 **Tailwind CSS** - Utility-first styling

### Developer Experience
- 🏗️ **Application Factory Pattern** - Clean Flask structure
- ⚙️ **Environment-Based Config** - Easy deployment configuration
- 🗄️ **SQLAlchemy ORM** - PostgreSQL/SQLite support
- 📦 **No Vendor Lock-in** - Deploy anywhere (Railway, Heroku, DigitalOcean)

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- pip
- PostgreSQL (production) or SQLite (development)
- Stripe account (for subscriptions)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/ReceiptForge.git
   cd ReceiptForge
   ```

2. **Create virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   ```

   Edit `.env` and add your values:
   ```env
   SESSION_SECRET=your-secret-key-here
   DATABASE_URL=sqlite:///receiptforge.db
   STRIPE_SECRET_KEY=sk_test_your_key
   STRIPE_WEBHOOK_SECRET=whsec_your_secret
   ```

5. **Initialize database**
   ```bash
   flask db upgrade
   ```

6. **Run the application**
   ```bash
   flask run
   ```

   Visit http://127.0.0.1:5000

## 📁 Project Structure

```
ReceiptForge/
├── app.py                  # Main Flask application
├── config.py               # Configuration management
├── models.py               # Database models
├── extensions.py           # Flask extensions
├── templates_data.py       # Receipt template definitions
│
├── templates/              # Jinja2 templates
│   ├── base.html          # Base template with nav/footer
│   ├── index.html         # Homepage
│   ├── templates.html     # Template listing
│   ├── template_detail.html
│   ├── generate_advanced_v2.html  # Receipt generator
│   ├── dashboard.html     # User dashboard
│   ├── pricing.html       # Pricing tiers
│   └── [18 landing pages]
│
├── static/                 # Static assets
│   ├── css/               # Tailwind compiled CSS
│   ├── js/                # JavaScript files
│   ├── images/            # Images and templates
│   └── fonts/             # Custom fonts
│
├── .env.example           # Environment template
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## ⚙️ Configuration

### Environment Variables

All configuration is managed through environment variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `SESSION_SECRET` | ✅ | Flask secret key (generate with `secrets.token_hex(32)`) |
| `DATABASE_URL` | ✅ | Database connection string |
| `STRIPE_SECRET_KEY` | ✅ | Stripe API secret key |
| `STRIPE_WEBHOOK_SECRET` | ✅ | Stripe webhook signing secret |
| `FLASK_ENV` | ❌ | Environment (development/production) |
| `DEBUG` | ❌ | Debug mode (true/false) |
| `ENABLE_SUBSCRIPTIONS` | ❌ | Enable Stripe subscriptions (default: true) |
| `PROGRAMMATIC_CONTENT_SOURCE` | ❌ | Single spreadsheet source (`.csv`, `.tsv`, `.xlsx`) |
| `PROGRAMMATIC_CONTENT_SHEET` | ❌ | Sheet name used when source is `.xlsx` |
| `PROGRAMMATIC_CONTENT_MANIFEST` | ❌ | Generated JSON manifest loaded by Flask |

### Database Setup

**SQLite (Development):**
```env
DATABASE_URL=sqlite:///receiptforge.db
```

**PostgreSQL (Production):**
```env
DATABASE_URL=postgresql://user:password@localhost:5432/receiptforge
```

### Stripe Configuration

1. Get your API keys from [Stripe Dashboard](https://dashboard.stripe.com/apikeys)
2. Set up webhook endpoint: `https://yourdomain.com/stripe-webhook`
3. Add webhook secret to `.env`

Required webhook events:
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.payment_succeeded`
- `invoice.payment_failed`

## Programmatic Backend

Use one spreadsheet to manage both SEO pages and tool pages.

1. Fill `content/programmatic_content.csv` (or replace with `.xlsx`).
2. Generate all routes at once:
   ```bash
   python3 scripts/generate_programmatic_content.py
   ```
   Or run the automation wrapper:
   ```bash
   ./scripts/run_programmatic_pipeline.sh
   ```
3. Restart Flask, then open generated pages directly by their `route_path`.

Automation-friendly command:

```bash
PROGRAMMATIC_CONTENT_SOURCE=content/programmatic_content.csv \
PROGRAMMATIC_CONTENT_MANIFEST=static/data/programmatic_content_manifest.json \
python3 scripts/generate_programmatic_content.py
```

Registry endpoint:

- `/programmatic/content` shows all published generated entries.

Required spreadsheet columns:

- `entry_type` (`page` or `tool`)
- `route_path` (example: `/tools/walmart-receipt-generator`)
- `title`

Optional columns include `meta_description`, `intro`, `body`, CTA fields, `feature_bullets`, `faq_pairs`, `tags`, and `status`.

## 🎨 Design System

### Colors
- **Primary Orange:** `#FF6B35` (`bg-[#FF6B35]`)
- **Text Primary:** Gray-900 (`text-gray-900`)
- **Text Secondary:** Gray-600 (`text-gray-600`)
- **Borders:** Gray-900 2px (`border-2 border-gray-900`)
- **Backgrounds:** White / Gray-50

### Button Styles
```html
<!-- Primary Button -->
<a href="#" class="px-8 py-4 bg-[#FF6B35] text-white font-bold text-lg border-2 border-gray-900 shadow-[3px_3px_0_0_#000000] hover:shadow-[1px_1px_0_0_#000000] hover:translate-x-[2px] hover:translate-y-[2px] transition-all">
    Click Me
</a>

<!-- Secondary Button -->
<a href="#" class="px-8 py-4 bg-white text-gray-900 font-bold text-lg border-2 border-gray-900 shadow-[3px_3px_0_0_#000000] hover:shadow-[1px_1px_0_0_#000000] hover:translate-x-[2px] hover:translate-y-[2px] transition-all">
    Secondary
</a>
```

### Card Styles
```html
<div class="bg-white border-2 border-gray-900 rounded-lg shadow-[3px_3px_0_0_#000000] p-6">
    Card content
</div>
```

## 🚢 Deployment

### Railway

1. Install Railway CLI: `npm i -g @railway/cli`
2. Login: `railway login`
3. Initialize: `railway init`
4. Add PostgreSQL: `railway add`
5. Set environment variables in Railway dashboard
6. Deploy: `railway up`

### Heroku

```bash
heroku create your-app-name
heroku addons:create heroku-postgresql:mini
heroku config:set SESSION_SECRET=your-secret
heroku config:set STRIPE_SECRET_KEY=sk_live_...
git push heroku main
heroku run flask db upgrade
```

### DigitalOcean App Platform

1. Connect your GitHub repository
2. Set environment variables in dashboard
3. Add PostgreSQL database
4. Deploy automatically on push

## 🧪 Testing

```bash
# Run Flask development server
flask run --debug

# Test Stripe webhooks locally (requires Stripe CLI)
stripe listen --forward-to localhost:5000/stripe-webhook

# Test receipt generation
curl http://localhost:5000/generate-advanced
```

## 🔒 Security Checklist

- [ ] Change `SESSION_SECRET` to a strong random value
- [ ] Use environment variables for all secrets
- [ ] Enable HTTPS in production
- [ ] Configure CORS properly
- [ ] Set up rate limiting
- [ ] Enable CSRF protection
- [ ] Use Stripe test keys for development
- [ ] Regularly update dependencies

## 📝 Customization

### Adding New Receipt Templates

1. Define template in `templates_data.py`:
```python
{
    'id': 'my-store-receipt',
    'name': 'My Store',
    'category': 'Retail',
    'slug': 'my-store-receipt',
    # ... template configuration
}
```

2. Add preview image to `static/images/template-previews/`

### Customizing Design

- Update colors in templates (search/replace `#FF6B35`)
- Modify `static/css/output.css` for custom Tailwind
- Edit `base.html` for global navigation/footer changes

### Adding Authentication

The boilerplate has Flask-Login configured but authentication is stubbed. To implement:

1. Add email/password fields to User model
2. Create login/register routes
3. Implement password hashing (use `werkzeug.security`)
4. Or integrate OAuth (Google, GitHub, etc.)

## 🤝 Contributing

This is a boilerplate template - feel free to fork and customize for your needs!

## 📄 License

MIT License - feel free to use for personal or commercial projects.

## 🙏 Credits

- Flask framework
- Tailwind CSS
- Stripe payment processing
- ReportLab PDF generation
- Alpine.js for interactivity

## 📧 Support

For issues or questions, please open an issue on GitHub.

---

**Built with ❤️ for SaaS builders**

Ready to launch your receipt generation SaaS? Fork this repo and start building!
