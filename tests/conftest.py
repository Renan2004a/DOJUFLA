"""Fixtures compartilhadas dos testes."""
import os
import sys

import pytest
from werkzeug.security import generate_password_hash

# Garante que a raiz do projeto esteja no sys.path.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from config import Config  # noqa: E402
from database import db  # noqa: E402


class _BaseConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"


@pytest.fixture()
def app(tmp_path):
    class TestConfig(_BaseConfig):
        DATABASE = str(tmp_path / "test.db")
        RAG_DIR = str(tmp_path / "rag")
        DOCS_DIR = str(tmp_path / "documentos")
        DATA_FILE = str(tmp_path / "base_conhecimento.txt")
        INDEX_FILE = str(tmp_path / "rag" / "index.faiss")
        INDEX_META = str(tmp_path / "rag" / "meta.json")

    return create_app(TestConfig)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def make_user(app):
    """Cria um usuário e devolve o id."""

    def _make(username, role="usuario", password="senha123"):
        with app.app_context(), db() as conn:
            cursor = conn.execute(
                "INSERT INTO usuarios (username, password, role) VALUES (?, ?, ?)",
                (username, generate_password_hash(password), role),
            )
            return cursor.lastrowid

    return _make


@pytest.fixture()
def login(client):
    """Autentica direto pela sessão (sem passar pelo formulário)."""

    def _login(user_id):
        with client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True

    return _login


@pytest.fixture()
def query(app):
    """Executa um SELECT no banco de teste."""

    def _query(sql, params=()):
        with app.app_context(), db() as conn:
            return conn.execute(sql, params).fetchall()

    return _query
