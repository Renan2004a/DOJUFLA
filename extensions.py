"""Extensões Flask compartilhadas entre os blueprints."""
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Faça login para continuar."
login_manager.login_message_category = "erro"

csrf = CSRFProtect()
