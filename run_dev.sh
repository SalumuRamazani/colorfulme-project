#!/bin/bash
export FLASK_APP=app.py
export SESSION_SECRET=dev-secret-key-for-testing
export DATABASE_URL=sqlite:///receiptforge.db
export FLASK_ENV=development

echo "🚀 Starting Receipt SaaS Boilerplate on port 5003..."
echo "📍 Visit: http://127.0.0.1:5003"
echo ""

# Modify app.py to use port 5003
python3 -c "
from app import create_app
app = create_app()
print('✅ App initialized successfully!')
print('🎨 MakeMyReceipt design system loaded')
print('💳 Stripe ready (add keys to .env)')
print('')
app.run(host='0.0.0.0', port=5003, debug=True)
"
