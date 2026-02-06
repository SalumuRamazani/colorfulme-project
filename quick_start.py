#!/usr/bin/env python3
"""Quick start script for ReceiptForge"""
import os
import sys

# Set environment variables
os.environ['SESSION_SECRET'] = 'dev-secret-for-testing'
os.environ['DATABASE_URL'] = 'sqlite:///receiptforge.db'
os.environ['FLASK_ENV'] = 'development'

print("=" * 70)
print("🚀 ReceiptForge SaaS Boilerplate - WORKING VERSION")
print("=" * 70)
print()

try:
    from app import create_app

    app = create_app()

    print("✅ App initialized successfully!")
    print("🎨 MakeMyReceipt design loaded")
    print("💳 Stripe ready (add keys to .env)")
    print()
    print("=" * 70)
    print("📍 Server running at:")
    print("   http://localhost:5005")
    print("   http://127.0.0.1:5005")
    print()
    print("🔍 Pages to try:")
    print("   Homepage:  http://localhost:5005/")
    print("   Templates: http://localhost:5005/templates")
    print("   Generator: http://localhost:5005/generate-advanced")
    print("=" * 70)
    print()
    print("Press CTRL+C to stop")
    print()

    # Start server
    app.run(
        host='0.0.0.0',
        port=5005,
        debug=False,
        use_reloader=False
    )

except KeyboardInterrupt:
    print("\n\n👋 Server stopped")
    sys.exit(0)
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
