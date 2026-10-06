"""Administração: treinamento da IA (upload/reindex) e gestão de usuários."""
import logging
import os

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from config import Config
from database import db
from models import ROLE_LEVELS
from rag.vectorstore import rebuild_vectorstore, stats

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Treinamento da IA
# --------------------------------------------------------------------------- #
@admin_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if not current_user.is_moderator_or_above():
        return "⛔ Acesso negado", 403

    mensagem = request.args.get("msg")
    if request.method == "POST":
        mensagem = _receber_pdf()

    return render_template("upload.html", mensagem=mensagem, stats=stats())


@admin_bp.route("/retrain")
@login_required
def retrain():
    if not current_user.is_moderator_or_above():
        return "⛔ Acesso negado", 403

    try:
        vectorstore = rebuild_vectorstore()
        msg = f"✅ IA reindexada: {vectorstore.index.ntotal} vetores."
    except Exception as exc:  # noqa: BLE001
        logger.exception("Falha ao reindexar")
        msg = f"⚠️ Falha ao reindexar: {exc}"
    return redirect(url_for("admin.upload", msg=msg))


def _receber_pdf() -> str:
    arquivo = request.files.get("file")
    if not arquivo or not arquivo.filename.lower().endswith(".pdf"):
        return "⚠️ Envie apenas arquivos .pdf"

    filename = os.path.basename(arquivo.filename)
    os.makedirs(Config.DOCS_DIR, exist_ok=True)
    arquivo.save(os.path.join(Config.DOCS_DIR, filename))

    try:
        vectorstore = rebuild_vectorstore()
        return f"✅ PDF '{filename}' indexado. Base com {vectorstore.index.ntotal} vetores."
    except Exception as exc:  # noqa: BLE001
        logger.exception("Falha ao reindexar")
        return f"⚠️ PDF salvo, mas falha ao reindexar: {exc}"


# --------------------------------------------------------------------------- #
# Gestão de usuários
# --------------------------------------------------------------------------- #
@admin_bp.route("/usuarios")
@login_required
def usuarios():
    if not current_user.is_admin_or_above():
        return "⛔ Acesso negado", 403

    with db() as conn:
        rows = conn.execute(
            "SELECT id, username, role FROM usuarios ORDER BY id ASC"
        ).fetchall()

    gerenciáveis = [row for row in rows if current_user.can_manage(row["role"])]
    roles = (
        ["usuario", "moderador", "admin"]
        if current_user.is_super_admin()
        else ["usuario", "moderador"]
    )
    return render_template(
        "admin_usuarios.html",
        usuarios=gerenciáveis,
        roles=roles,
        erro=request.args.get("erro"),
        ok=request.args.get("ok"),
    )


@admin_bp.route("/usuarios/<int:user_id>/role", methods=["POST"])
@login_required
def alterar_role(user_id):
    if not current_user.is_admin_or_above():
        return _voltar("Acesso negado.")

    novo_role = request.form.get("role")
    if novo_role not in ROLE_LEVELS:
        return _voltar("Cargo inválido.")
    if novo_role == "super_admin":
        return _voltar("super_admin só pode ser definido via script.")

    with db() as conn:
        alvo = conn.execute(
            "SELECT id, username, role FROM usuarios WHERE id=?", (user_id,)
        ).fetchone()
        if alvo is None:
            return _voltar("Usuário não encontrado.")
        if not current_user.can_manage(alvo["role"]):
            return _voltar("Você só pode gerenciar usuários de nível inferior ao seu.")
        if novo_role == "admin" and not current_user.is_super_admin():
            return _voltar("Apenas super_admin pode promover a admin.")
        if ROLE_LEVELS[novo_role] >= current_user.level():
            return _voltar("Não é possível atribuir cargo igual ou superior ao seu.")

        conn.execute("UPDATE usuarios SET role=? WHERE id=?", (novo_role, user_id))

    return redirect(
        url_for("admin.usuarios", ok=f"Cargo de '{alvo['username']}' atualizado para {novo_role}.")
    )


def _voltar(erro: str):
    return redirect(url_for("admin.usuarios", erro=erro))
