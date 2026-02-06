#!/usr/bin/env python3
"""
Simple server startup script for Receipt SaaS Boilerplate
"""
import os
import sys

# Set environment variables
os.environ['SESSION_SECRET'] = 'dev-secret-key-for-testing-only'
os.environ['DATABASE_URL'] = 'sqlite:///receiptforge.db'
os.environ['FLASK_ENV'] = 'development'
os.environ['DEBUG'] = 'true'

print("🚀 Starting Receipt SaaS Boilerplate...")
print("=" * 60)
print()

try:
    from app import create_app

    app = create_app()

    print("✅ App initialized successfully!")
    print("🎨 MakeMyReceipt design system loaded")
    print("🎯 100+ receipt templates ready")
    print("💳 Stripe integration ready (add keys to .env)")
    print()
    print("=" * 60)
    print("📍 Server running at:")
    print("   http://127.0.0.1:5003")
    print("   http://localhost:5003")
    print()
    print("🔍 Try these pages:")
    print("   Homepage:  http://127.0.0.1:5003/")
    print("   Templates: http://127.0.0.1:5003/templates")
    print("   Pricing:   http://127.0.0.1:5003/pricing")
    print("=" * 60)
    print()
    print("Press CTRL+C to stop the server")
    print()

    # Run the app
    app.run(
        host='0.0.0.0',
        port=5003,
        debug=True,
        use_reloader=False  # Prevent double startup
    )

except KeyboardInterrupt:
    print("\n\n👋 Server stopped. Goodbye!")
    sys.exit(0)
except Exception as e:
    print(f"\n❌ Error starting server: {e}")
    print("\nTroubleshooting:")
    print("1. Check if dependencies are installed: pip install -r requirements.txt")
    print("2. Make sure port 5003 is available")
    print("3. Check the error message above for details")
    sys.exit(1)
