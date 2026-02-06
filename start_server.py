#!/usr/bin/env python3
import os
from app import create_app

os.environ.setdefault('SESSION_SECRET', 'dev-secret-key-for-testing')
os.environ.setdefault('DATABASE_URL', 'sqlite:///colorfulme.db')
os.environ.setdefault('DEBUG', 'true')
os.environ.setdefault('PORT', '5003')

app = create_app()

print('ColorfulMe server ready')
print('http://127.0.0.1:5003')
app.run(host='0.0.0.0', port=5003, debug=True, use_reloader=False)
