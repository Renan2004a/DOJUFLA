"""Chat com streaming, histórico de conversas e preferência de LLM."""
import json
import logging

from flask import (
    Blueprint,
    Response,
    jsonify,
    render_template,
    request,
    stream_with_context,
)
from flask_login import current_user, login_required

from config import Config
from database import db
from rag.llm import available_providers, gerar_resposta
from rag.vectorstore import get_vectorstore, retrieve_with_sources
from rag import websearch

chat_bp = Blueprint("chat", __name__)
logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Páginas
# --------------------------------------------------------------------------- #
@chat_bp.route("/")
@login_required
def home():
    return render_template("index.html", llms=available_providers())


@chat_bp.route("/institucional")
def sobre():
    return render_template("sobre.html")


# --------------------------------------------------------------------------- #
# Preferência de LLM
# --------------------------------------------------------------------------- #
@chat_bp.post("/set_llm")
@login_required
def set_llm():
    data = request.get_json(silent=True) or {}
    llm = data.get("llm", "")
    if llm not in {provider["name"] for provider in available_providers()}:
        return jsonify({"erro": "Modelo indisponível"}), 400

    with db() as conn:
        conn.execute(
            "UPDATE usuarios SET llm_preference=? WHERE id=?", (llm, current_user.id)
        )
    current_user.llm_preference = llm
    return jsonify({"ok": True, "llm": llm})


# --------------------------------------------------------------------------- #
# Histórico de conversas
# --------------------------------------------------------------------------- #
@chat_bp.get("/conversas")
@login_required
def listar_conversas():
    with db() as conn:
        rows = conn.execute(
            "SELECT id, titulo, created_at, updated_at FROM conversas "
            "WHERE user_id=? ORDER BY updated_at DESC, id DESC",
            (current_user.id,),
        ).fetchall()
    return jsonify([dict(row) for row in rows])


@chat_bp.get("/conversa/<int:conversa_id>")
@login_required
def obter_conversa(conversa_id):
    with db() as conn:
        if not _usuario_dono(conn, conversa_id):
            return jsonify({"erro": "Conversa não encontrada"}), 404
        rows = conn.execute(
            "SELECT pergunta, resposta, fontes FROM historico "
            "WHERE conversa_id=? ORDER BY id ASC",
            (conversa_id,),
        ).fetchall()
    return jsonify({
        "conversa_id": conversa_id,
        "mensagens": [
            {
                "pergunta": row["pergunta"],
                "resposta": row["resposta"],
                "fontes": _parse_fontes(row["fontes"]),
            }
            for row in rows
        ],
    })


@chat_bp.post("/conversa/nova")
@login_required
def nova_conversa():
    with db() as conn:
        cursor = conn.execute(
            "INSERT INTO conversas (user_id, titulo) VALUES (?, 'Nova Conversa')",
            (current_user.id,),
        )
        conversa_id = cursor.lastrowid
    return jsonify({"conversa_id": conversa_id, "titulo": "Nova Conversa"})


@chat_bp.post("/conversa/<int:conversa_id>/renomear")
@login_required
def renomear_conversa(conversa_id):
    titulo = (request.get_json(silent=True) or {}).get("titulo", "").strip()
    if not titulo:
        return jsonify({"erro": "Título vazio"}), 400

    titulo = titulo[:80]
    with db() as conn:
        cursor = conn.execute(
            "UPDATE conversas SET titulo=? WHERE id=? AND user_id=?",
            (titulo, conversa_id, current_user.id),
        )
        if cursor.rowcount == 0:
            return jsonify({"erro": "Conversa não encontrada"}), 404
    return jsonify({"ok": True, "titulo": titulo})


@chat_bp.route("/conversa/<int:conversa_id>/deletar", methods=["DELETE", "POST"])
@login_required
def deletar_conversa(conversa_id):
    with db() as conn:
        conn.execute(
            "DELETE FROM historico WHERE conversa_id=? AND user_id=?",
            (conversa_id, current_user.id),
        )
        conn.execute(
            "DELETE FROM conversas WHERE id=? AND user_id=?",
            (conversa_id, current_user.id),
        )
    return jsonify({"ok": True})


@chat_bp.get("/conversa/<int:conversa_id>/exportar")
@login_required
def exportar_conversa(conversa_id):
    with db() as conn:
        conversa = conn.execute(
            "SELECT titulo FROM conversas WHERE id=? AND user_id=?",
            (conversa_id, current_user.id),
        ).fetchone()
        if not conversa:
            return jsonify({"erro": "Conversa não encontrada"}), 404
        rows = conn.execute(
            "SELECT pergunta, resposta, fontes FROM historico "
            "WHERE conversa_id=? ORDER BY id ASC",
            (conversa_id,),
        ).fetchall()

    linhas = [f"# {conversa['titulo']}", ""]
    for row in rows:
        linhas.append(f"## Você\n\n{row['pergunta']}\n")
        linhas.append(f"## Assistente\n\n{row['resposta']}\n")
        fontes = _parse_fontes(row["fontes"])
        if fontes:
            linhas.append("Fontes: " + "; ".join(_rotulo_fonte(f) for f in fontes) + "\n")

    return Response(
        "\n".join(linhas),
        mimetype="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="conversa-{conversa_id}.md"'},
    )


# --------------------------------------------------------------------------- #
# Pergunta (resposta em streaming)
# --------------------------------------------------------------------------- #
@chat_bp.post("/ask")
@login_required
def ask():
    data = request.get_json(silent=True) or {}
    pergunta = (data.get("question") or "").strip()
    if not pergunta:
        return Response("Pergunta vazia", status=400)

    user_id = current_user.id
    conversa_id = _resolver_conversa(user_id, data.get("conversa_id"), pergunta)
    historico = _carregar_historico(conversa_id)

    trechos = retrieve_with_sources(pergunta, get_vectorstore())
    usar_web = bool(data.get("web", Config.WEB_SEARCH_ENABLED))
    trechos_web = websearch.search(pergunta) if usar_web else []

    partes = [item["texto"] for item in trechos]
    for item in trechos_web:
        partes.append(f"[Fonte web: {item['titulo']} — {item['url']}]\n{item['trecho']}")
    contexto = "\n\n".join(partes)

    fontes = _fontes_local(trechos) + _fontes_web(trechos_web)
    fontes_json = json.dumps(fontes, ensure_ascii=False)
    llm = current_user.llm_preference

    def gerar():
        resposta = ""
        try:
            for token in gerar_resposta(
                contexto, pergunta, historico=historico, stream=True, llm=llm
            ):
                resposta += token
                yield token
        except Exception as exc:  # noqa: BLE001 - devolve o erro ao usuário
            logger.exception("Erro ao gerar resposta")
            mensagem = f"\n[ERRO ao gerar resposta: {exc}]"
            resposta += mensagem
            yield mensagem
        finally:
            _salvar_mensagem(user_id, conversa_id, pergunta, resposta, fontes_json)

    response = Response(stream_with_context(gerar()), content_type="text/plain")
    response.headers["X-Conversa-ID"] = str(conversa_id)
    # Cabeçalhos precisam ser ASCII; o front desserializa com JSON.parse.
    response.headers["X-Sources"] = json.dumps(fontes, ensure_ascii=True)
    return response


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _usuario_dono(conn, conversa_id: int) -> bool:
    return conn.execute(
        "SELECT 1 FROM conversas WHERE id=? AND user_id=?",
        (conversa_id, current_user.id),
    ).fetchone() is not None


def _resolver_conversa(user_id: int, conversa_id, pergunta: str) -> int:
    """Garante uma conversa válida do usuário; cria/renomeia quando preciso."""
    titulo = pergunta[:30] + ("..." if len(pergunta) > 30 else "")
    with db() as conn:
        if conversa_id:
            row = conn.execute(
                "SELECT id, titulo FROM conversas WHERE id=? AND user_id=?",
                (conversa_id, user_id),
            ).fetchone()
            if row and row["titulo"] != "Nova Conversa":
                return conversa_id
            if row:
                conn.execute("UPDATE conversas SET titulo=? WHERE id=?", (titulo, conversa_id))
                return conversa_id

        cursor = conn.execute(
            "INSERT INTO conversas (user_id, titulo) VALUES (?, ?)", (user_id, titulo)
        )
        return cursor.lastrowid


def _carregar_historico(conversa_id: int) -> list:
    """Últimas mensagens da conversa, das mais antigas para as mais novas."""
    with db() as conn:
        rows = conn.execute(
            "SELECT pergunta, resposta FROM historico WHERE conversa_id=? "
            "ORDER BY id DESC LIMIT ?",
            (conversa_id, Config.HISTORY_LIMIT),
        ).fetchall()

    historico = []
    for row in reversed(rows):
        historico.append(f"Usuário: {row['pergunta']}")
        historico.append(f"Assistente: {row['resposta']}")
    return historico


def _salvar_mensagem(user_id: int, conversa_id: int, pergunta: str, resposta: str,
                     fontes_json: str) -> None:
    try:
        with db() as conn:
            conn.execute(
                "INSERT INTO historico (conversa_id, user_id, pergunta, resposta, fontes) "
                "VALUES (?, ?, ?, ?, ?)",
                (conversa_id, user_id, pergunta, resposta, fontes_json),
            )
            conn.execute(
                "UPDATE conversas SET updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (conversa_id,),
            )
    except Exception:  # pragma: no cover - não deve quebrar a resposta
        logger.exception("Falha ao salvar a mensagem no histórico")


def _fontes_local(trechos: list) -> list:
    vistos = set()
    fontes = []
    for item in trechos:
        chave = (item["arquivo"], item["pagina"])
        if chave not in vistos:
            vistos.add(chave)
            fontes.append({
                "tipo": "local",
                "arquivo": item["arquivo"],
                "pagina": item["pagina"],
            })
    return fontes


def _fontes_web(resultados: list) -> list:
    return [
        {"tipo": "web", "titulo": item["titulo"], "url": item["url"]}
        for item in resultados
    ]


def _parse_fontes(raw) -> list:
    if not raw:
        return []
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return []


def _rotulo_fonte(fonte: dict) -> str:
    if fonte.get("tipo") == "web":
        return fonte.get("url") or fonte.get("titulo") or "web"
    arquivo = fonte.get("arquivo", "?")
    pagina = fonte.get("pagina")
    return f"{arquivo} (p. {pagina})" if pagina else arquivo
