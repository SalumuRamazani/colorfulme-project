#!/bin/bash
export FLASK_APP=app.py
export SESSION_SECRET=dev-secret-key-for-testing
export DATABASE_URL=sqlite:///receiptforge.db
export FLASK_ENV=development

echo "🚀 Starting Receipt SaaS Boilerplate..."
echo "📍 Running on: http://127.0.0.1:5003"
echo ""
python3 app.py
