"""Shared Flask extension instances."""

from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Bitte melden Sie sich an, um diese Seite aufzurufen."
login_manager.login_message_category = "warning"
