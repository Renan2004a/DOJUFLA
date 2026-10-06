"""Ponto de entrada da aplicação DOJUFLA.

Cria a aplicação Flask, registra os blueprints e — quando executado
diretamente — sobe o servidor de desenvolvimento em http://127.0.0.1:5002.
"""
import logging
import sys

from flask import Flask

from blueprints.admin import admin_bp
from blueprints.auth import auth_bp
from blueprints.chat import chat_bp
from config import Config
from database import init_db
from extensions import login_manager
from models import get_user


def _configure_stdout() -> None:
    """Garante saída UTF-8 no terminal (evita erros com acentos no Windows)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:  # pragma: no cover - streams sem suporte
            pass


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def create_app(config_object=Config) -> Flask:
    """Cria e configura a aplicação Flask."""
    _configure_stdout()
    _configure_logging()

    app = Flask(__name__)
    app.config.from_object(config_object)

    with app.app_context():
        init_db()

    login_manager.init_app(app)
    login_manager.user_loader(get_user)

    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(admin_bp)

    app.logger.info("DOJUFLA pronto | banco: %s", app.config["DATABASE"])
    return app


if __name__ == "__main__":
    # use_reloader=False evita carregar o modelo de embeddings duas vezes.
    create_app().run(debug=True, port=5002, use_reloader=False)
