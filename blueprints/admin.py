"""Administração: treinamento da IA (upload/reindex) e gestão de usuários."""
import logging
import os

from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from config import Config
from database import db
from models import ROLE_LEVELS
from rag import indexer
from rag.vectorstore import stats

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
        mensagem = _receber_arquivos()

    return render_template("upload.html", mensagem=mensagem, stats=stats(),
                           progresso=indexer.status())


@admin_bp.route("/retrain", methods=["GET", "POST"])
@login_required
def retrain():
    if not current_user.is_moderator_or_above():
        return "⛔ Acesso negado", 403

    if indexer.start():
        msg = "🔄 Reindexação iniciada. Acompanhe o progresso abaixo."
    else:
        msg = "⏳ Já existe uma reindexação em andamento."
    return redirect(url_for("admin.upload", msg=msg))


@admin_bp.get("/reindex_status")
@login_required
def reindex_status():
    if not current_user.is_moderator_or_above():
        return jsonify({"erro": "Acesso negado"}), 403
    return jsonify(indexer.status())


def _receber_arquivos() -> str:
    arquivos = [f for f in request.files.getlist("file") if f and f.filename]
    if not arquivos:
        return "⚠️ Nenhum arquivo enviado."

    salvos, ignorados = [], []
    os.makedirs(Config.DOCS_DIR, exist_ok=True)
    for arquivo in arquivos:
        ext = os.path.splitext(arquivo.filename)[1].lower()
        if ext not in Config.ALLOWED_EXTENSIONS:
            ignorados.append(arquivo.filename)
            continue
        filename = os.path.basename(arquivo.filename)
        arquivo.save(os.path.join(Config.DOCS_DIR, filename))
        salvos.append(filename)

    if not salvos:
        return f"⚠️ Formatos não aceitos: {', '.join(ignorados)}."

    iniciada = indexer.start()
    partes = [f"✅ {len(salvos)} arquivo(s) enviado(s)."]
    if ignorados:
        partes.append(f"Ignorados (formato): {', '.join(ignorados)}.")
    partes.append(
        "🔄 Reindexação iniciada." if iniciada else "⏳ Reindexação já em andamento."
    )
    return " ".join(partes)


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
