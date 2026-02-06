"""
Flask extensions initialization module.
Extensions are created here without binding to the app to avoid circular imports.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

# Initialize extensions without binding to app
db = SQLAlchemy()
login_manager = LoginManager()
