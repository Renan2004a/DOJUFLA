"""Autenticação: login, cadastro e logout."""
from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from database import db
from models import user_from_row

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("acao") == "register":
            return _register()
        return _login()
    return render_template("login.html", modo="login")


@auth_bp.route("/register")
def register():
    """Mantém o link antigo, redirecionando para a aba de cadastro."""
    return redirect(url_for("auth.login") + "#cadastro")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


def _register():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    if not username or not password:
        return render_template("login.html", erro_cad="Preencha todos os campos", modo="cadastro")

    with db() as conn:
        existente = conn.execute(
            "SELECT 1 FROM usuarios WHERE username=?", (username,)
        ).fetchone()
        if existente:
            return render_template("login.html", erro_cad="Usuário já existe", modo="cadastro")
        conn.execute(
            "INSERT INTO usuarios (username, password, role, llm_preference) "
            "VALUES (?, ?, 'usuario', ?)",
            (username, generate_password_hash(password), Config.DEFAULT_LLM),
        )

    return render_template("login.html", sucesso="Conta criada! Faça login.", modo="login")


def _login():
    username = request.form.get("username", "")
    password = request.form.get("password", "")

    with db() as conn:
        row = conn.execute("SELECT * FROM usuarios WHERE username=?", (username,)).fetchone()

    if row and check_password_hash(row["password"], password):
        login_user(user_from_row(row), remember=True)
        return redirect(url_for("chat.home"))

    return render_template("login.html", erro="Login inválido", modo="login")
