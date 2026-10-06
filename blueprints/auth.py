"""Autenticação: login (com limite de tentativas), cadastro, logout e conta."""
import threading
import time

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from database import db
from models import user_from_row

auth_bp = Blueprint("auth", __name__)

# Controle simples de tentativas de login: chave -> lista de timestamps.
_attempts = {}
_attempts_lock = threading.Lock()


# --------------------------------------------------------------------------- #
# Login / cadastro / logout
# --------------------------------------------------------------------------- #
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
    if len(password) < Config.PASSWORD_MIN_LENGTH:
        return render_template(
            "login.html",
            erro_cad=f"A senha deve ter ao menos {Config.PASSWORD_MIN_LENGTH} caracteres.",
            modo="cadastro",
        )

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
    chave = f"{username}|{request.remote_addr}"

    if _bloqueado(chave):
        return render_template(
            "login.html",
            erro="Muitas tentativas. Aguarde alguns minutos e tente novamente.",
            modo="login",
        )

    with db() as conn:
        row = conn.execute("SELECT * FROM usuarios WHERE username=?", (username,)).fetchone()

    if row and check_password_hash(row["password"], password):
        _limpar_tentativas(chave)
        login_user(user_from_row(row), remember=True)
        return redirect(url_for("chat.home"))

    _registrar_falha(chave)
    return render_template("login.html", erro="Login inválido", modo="login")


# --------------------------------------------------------------------------- #
# Conta
# --------------------------------------------------------------------------- #
@auth_bp.route("/conta")
@login_required
def conta():
    return render_template("conta.html")


@auth_bp.route("/conta/senha", methods=["POST"])
@login_required
def alterar_senha():
    atual = request.form.get("atual", "")
    nova = request.form.get("nova", "")

    with db() as conn:
        row = conn.execute(
            "SELECT password FROM usuarios WHERE id=?", (current_user.id,)
        ).fetchone()
        if not row or not check_password_hash(row["password"], atual):
            return render_template("conta.html", erro="Senha atual incorreta.")
        if len(nova) < Config.PASSWORD_MIN_LENGTH:
            return render_template(
                "conta.html",
                erro=f"A nova senha deve ter ao menos {Config.PASSWORD_MIN_LENGTH} caracteres.",
            )
        conn.execute(
            "UPDATE usuarios SET password=? WHERE id=?",
            (generate_password_hash(nova), current_user.id),
        )

    return render_template("conta.html", ok="Senha alterada com sucesso.")


# --------------------------------------------------------------------------- #
# Limite de tentativas
# --------------------------------------------------------------------------- #
def _bloqueado(chave: str) -> bool:
    agora = time.time()
    with _attempts_lock:
        tentativas = [t for t in _attempts.get(chave, []) if agora - t < Config.LOGIN_WINDOW_SECONDS]
        _attempts[chave] = tentativas
        return len(tentativas) >= Config.LOGIN_MAX_ATTEMPTS


def _registrar_falha(chave: str) -> None:
    with _attempts_lock:
        _attempts.setdefault(chave, []).append(time.time())


def _limpar_tentativas(chave: str) -> None:
    with _attempts_lock:
        _attempts.pop(chave, None)
