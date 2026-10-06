import os

# Carrega variáveis de um arquivo .env (se existir) ANTES de importar os módulos
# que leem segredos (GROQ_API_KEY etc.). Em produção, use as variáveis de ambiente.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except Exception:
    pass

from flask import Flask, render_template, request, redirect, Response, url_for, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db, init_db, DB_PATH
from rag.vectorstore import create_vectorstore, retrieve
from rag.llm import gerar_resposta
import sys
import sqlite3
import traceback

# Garante saída UTF-8 no terminal (evita UnicodeEncodeError com emojis no Windows).
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# Caminhos absolutos a partir da pasta do app (funciona de qualquer diretório).
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(BASE_DIR, "documentos")

app = Flask(__name__)
app.secret_key = os.environ.get("DOJUFLA_SECRET_KEY", "secret_dojufla_key")

# ================= DIAGNÓSTICO INICIAL =================
print("=" * 60)
print("PASTA DO APP:", BASE_DIR)
print("BANCO EM USO:", DB_PATH)
print("EXISTE?     :", os.path.exists(DB_PATH))

init_db()

if os.path.exists(DB_PATH):
    _c = sqlite3.connect(DB_PATH)
    try:
        cols_hist = [r[1] for r in _c.execute("PRAGMA table_info(historico)").fetchall()]
        cols_conv = [r[1] for r in _c.execute("PRAGMA table_info(conversas)").fetchall()]
        cols_user = [r[1] for r in _c.execute("PRAGMA table_info(usuarios)").fetchall()]
        print("COLUNAS historico:", cols_hist)
        print("COLUNAS conversas:", cols_conv)
        print("COLUNAS usuarios :", cols_user)
        if "conversa_id" not in cols_hist:
            print("❌ ERRO: coluna 'conversa_id' NÃO existe em historico!")
        else:
            print("✅ Coluna 'conversa_id' presente.")
    except Exception as e:
        print("Erro ao inspecionar tabelas:", e)
    finally:
        _c.close()
print("=" * 60)


# ================= LOGIN MANAGER =================
login_manager = LoginManager(app)
login_manager.login_view = "login"


# ================= HIERARQUIA =================
ROLE_LEVELS = {
    "usuario": 1,
    "moderador": 2,
    "admin": 3,
    "super_admin": 4,
}


class User(UserMixin):
    def __init__(self, id, username, role, llm_preference="ollama"):
        self.id = id
        self.username = username
        self.role = role if role in ROLE_LEVELS else "usuario"
        self.llm_preference = llm_preference

    @property
    def is_admin(self):
        return self.role in ("admin", "super_admin")

    def level(self):
        return ROLE_LEVELS.get(self.role, 1)

    def is_moderator_or_above(self):
        return self.level() >= ROLE_LEVELS["moderador"]

    def is_admin_or_above(self):
        return self.level() >= ROLE_LEVELS["admin"]

    def is_super_admin(self):
        return self.role == "super_admin"

    def can_manage(self, other_role):
        return self.level() > ROLE_LEVELS.get(other_role, 0)


@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM usuarios WHERE id=?", (user_id,)).fetchone()
    conn.close()

    if user:
        role = user["role"] if "role" in user.keys() else "usuario"
        llm_pref = user["llm_preference"] if "llm_preference" in user.keys() else "ollama"
        return User(user["id"], user["username"], role, llm_pref)
    return None


# ================= VETORSTORE =================
try:
    index, docs = create_vectorstore()
    print(f"✅ Vectorstore carregado: {index.ntotal} vetores, {len(docs)} blocos")
except Exception as e:
    print(f"⚠️ Falha ao carregar vectorstore: {e}")
    traceback.print_exc()
    index, docs = None, []


def kb_stats():
    """Resumo da base de conhecimento indexada (para confirmar o 'treinamento')."""
    total_pdfs = 0
    if os.path.isdir(DOCS_DIR):
        total_pdfs = len([f for f in os.listdir(DOCS_DIR) if f.lower().endswith(".pdf")])
    return {
        "modelo": "all-MiniLM-L6-v2",
        "vetores": index.ntotal if index is not None else 0,
        "blocos": len(docs),
        "pdfs": total_pdfs,
    }


# ================= ROTAS DE PÁGINAS =================

@app.route("/")
@login_required
def home():
    return render_template("index.html")


@app.route("/institucional")
def sobre():
    return render_template("sobre.html")


# ================= AUTENTICAÇÃO =================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        acao = request.form.get("acao", "login")

        if acao == "register":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()

            if not username or not password:
                return render_template("login.html", erro_cad="Preencha todos os campos", modo="cadastro")

            conn = get_db()
            existe = conn.execute("SELECT * FROM usuarios WHERE username=?", (username,)).fetchone()
            if existe:
                conn.close()
                return render_template("login.html", erro_cad="Usuário já existe", modo="cadastro")

            conn.execute(
                "INSERT INTO usuarios (username, password, role) VALUES (?, ?, 'usuario')",
                (username, generate_password_hash(password))
            )
            conn.commit()
            conn.close()

            return render_template("login.html", sucesso="Conta criada! Faça login.", modo="login")

        username = request.form.get("username", "")
        password = request.form.get("password", "")

        conn = get_db()
        user = conn.execute("SELECT * FROM usuarios WHERE username=?", (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            role = user["role"] if "role" in user.keys() else "usuario"
            llm_pref = user["llm_preference"] if "llm_preference" in user.keys() else "ollama"
            login_user(User(user["id"], user["username"], role, llm_pref), remember=True)
            return redirect(url_for("home"))

        return render_template("login.html", erro="Login inválido", modo="login")

    return render_template("login.html", modo="login")


@app.route("/register")
def register():
    return redirect(url_for("login") + "#cadastro")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ================= CONFIGURAÇÕES DE LLM =================

@app.route("/set_llm", methods=["POST"])
@login_required
def set_llm():
    data = request.get_json()
    llm = data.get("llm", "ollama")
    if llm not in ["ollama", "groq"]:
        return jsonify({"erro": "LLM inválido"}), 400

    conn = get_db()
    conn.execute("UPDATE usuarios SET llm_preference=? WHERE id=?", (llm, current_user.id))
    conn.commit()
    conn.close()
    current_user.llm_preference = llm
    return jsonify({"ok": True, "llm": llm})


# ================= CONVERSAS =================

@app.route("/conversas", methods=["GET"])
@login_required
def listar_conversas():
    conn = get_db()
    conversas = conn.execute(
        "SELECT id, titulo, created_at, updated_at FROM conversas WHERE user_id=? ORDER BY updated_at DESC, id DESC",
        (current_user.id,)
    ).fetchall()
    conn.close()
    return jsonify([
        {
            "id": c["id"],
            "titulo": c["titulo"],
            "created_at": c["created_at"],
            "updated_at": c["updated_at"],
        }
        for c in conversas
    ])


@app.route("/conversa/<int:conversa_id>", methods=["GET"])
@login_required
def obter_conversa(conversa_id):
    print(f"[obter_conversa] 🔍 Buscando conversa {conversa_id} para user {current_user.id}")

    conn = get_db()
    conversa = conn.execute(
        "SELECT id FROM conversas WHERE id=? AND user_id=?",
        (conversa_id, current_user.id)
    ).fetchone()

    if not conversa:
        conn.close()
        print(f"[obter_conversa] ❌ conversa {conversa_id} não encontrada")
        return jsonify({"erro": "Conversa não encontrada"}), 404

    mensagens = conn.execute(
        "SELECT id, pergunta, resposta FROM historico WHERE conversa_id=? ORDER BY id ASC",
        (conversa_id,)
    ).fetchall()
    conn.close()

    print(f"[obter_conversa] ✅ conversa {conversa_id}: {len(mensagens)} mensagens no banco")

    for m in mensagens:
        print(f"    id={m['id']} P={m['pergunta'][:40]!r}")

    return jsonify({
        "conversa_id": conversa_id,
        "mensagens": [{"pergunta": m["pergunta"], "resposta": m["resposta"]} for m in mensagens]
    })


@app.route("/conversa/nova", methods=["POST"])
@login_required
def nova_conversa():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO conversas (user_id, titulo) VALUES (?, ?)",
        (current_user.id, "Nova Conversa")
    )
    conversa_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return jsonify({"conversa_id": conversa_id, "titulo": "Nova Conversa"})


@app.route("/conversa/<int:conversa_id>/deletar", methods=["DELETE", "POST"])
@login_required
def deletar_conversa(conversa_id):
    conn = get_db()
    conn.execute("DELETE FROM historico WHERE conversa_id=? AND user_id=?", (conversa_id, current_user.id))
    conn.execute("DELETE FROM conversas WHERE id=? AND user_id=?", (conversa_id, current_user.id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ================= CHAT (STREAMING) =================

@app.route("/ask", methods=["POST"])
@login_required
def ask():
    print("\n" + "=" * 60)
    print("[ask] 🚀 Requisição recebida")

    data = request.get_json()
    pergunta = data.get("question", "").strip()
    conversa_id = data.get("conversa_id")
    user_id = current_user.id

    print(f"[ask] user={user_id} pergunta={pergunta!r} conversa_id={conversa_id}")

    if not pergunta:
        return Response("Pergunta vazia", status=400)

    conn = get_db()

    if not conversa_id:
        titulo = pergunta[:30] + ("..." if len(pergunta) > 30 else "")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO conversas (user_id, titulo) VALUES (?, ?)",
            (user_id, titulo)
        )
        conversa_id = cursor.lastrowid
        conn.commit()
        print(f"[ask] ✅ Nova conversa criada: id={conversa_id}")
    else:
        conversa = conn.execute("SELECT titulo FROM conversas WHERE id=?", (conversa_id,)).fetchone()
        if conversa and conversa["titulo"] == "Nova Conversa":
            titulo = pergunta[:30] + ("..." if len(pergunta) > 30 else "")
            conn.execute("UPDATE conversas SET titulo=? WHERE id=?", (titulo, conversa_id))
            conn.commit()
            print(f"[ask] ✅ Conversa {conversa_id} renomeada para {titulo!r}")

    historico_mensagens = conn.execute(
        "SELECT pergunta, resposta FROM historico WHERE conversa_id=? ORDER BY id ASC LIMIT 6",
        (conversa_id,)
    ).fetchall()
    conn.close()

    historico_prompt = []
    for h in historico_mensagens:
        historico_prompt.append(f"Usuário: {h['pergunta']}")
        historico_prompt.append(f"Assistente: {h['resposta']}")

    if index is not None and docs:
        try:
            contexto = "\n\n".join(retrieve(pergunta, index, docs))
            print(f"[ask] 📚 {len(contexto)} chars de contexto")
        except Exception as e:
            contexto = ""
            print(f"[ask] ⚠️ Erro no retrieve: {e}")
    else:
        contexto = ""
        print("[ask] ⚠️ Sem vectorstore")

    llm_escolhido = current_user.llm_preference
    print(f"[ask] 🤖 LLM={llm_escolhido}")
    print(f"[ask] 🎬 Iniciando gerador...")

    def gerar():
        resposta_completa = ""
        tokens_recebidos = 0

        # ---- Geração ----
        try:
            for token in gerar_resposta(contexto, pergunta, historico=historico_prompt,
                                        stream=True, llm=llm_escolhido):
                resposta_completa += token
                tokens_recebidos += 1
                yield token
            print(f"[ask] ✅ Gerador concluído: {tokens_recebidos} tokens")
        except Exception as e:
            erro_msg = f"\n[ERRO ao gerar resposta: {e}]"
            resposta_completa += erro_msg
            yield erro_msg
            print(f"[ask] ❌ Erro no gerador: {e}")
            traceback.print_exc()

        # ---- Salvamento no histórico (SEMPRE roda) ----
        print(f"[ask] 💾 Salvando histórico: conversa_id={conversa_id}, "
              f"pergunta={len(pergunta)} chars, resposta={len(resposta_completa)} chars")

        try:
            c = get_db()
            cursor = c.cursor()
            cursor.execute(
                "INSERT INTO historico (conversa_id, user_id, pergunta, resposta) VALUES (?, ?, ?, ?)",
                (conversa_id, user_id, pergunta, resposta_completa)
            )
            hist_id = cursor.lastrowid
            c.execute("UPDATE conversas SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (conversa_id,))
            c.commit()

            # Confirma que salvou
            check = c.execute("SELECT COUNT(*) FROM historico WHERE conversa_id=?", (conversa_id,)).fetchone()[0]
            c.close()

            print(f"[ask] ✅ Histórico SALVO: id={hist_id}, "
                  f"total de mensagens na conversa {conversa_id} = {check}")
        except Exception as e:
            print(f"[ask] ❌❌❌ ERRO AO SALVAR NO HISTÓRICO: {e}")
            traceback.print_exc()

        print("[ask] 🏁 Requisição finalizada")
        print("=" * 60 + "\n")

    response = Response(gerar(), content_type="text/plain")
    response.headers["X-Conversa-ID"] = str(conversa_id)
    return response


# ================= ADMIN: UPLOAD / RETRAIN =================

@app.route("/admin/upload", methods=["GET", "POST"])
@login_required
def upload():
    if not current_user.is_moderator_or_above():
        return "⛔ Acesso negado"

    mensagem = request.args.get("msg")
    if request.method == "POST":
        file = request.files.get("file")
        if file and file.filename.lower().endswith(".pdf"):
            filename = os.path.basename(file.filename)
            os.makedirs(DOCS_DIR, exist_ok=True)
            caminho = os.path.join(DOCS_DIR, filename)
            file.save(caminho)

            global index, docs
            try:
                from rag.vectorstore import rebuild_vectorstore
                index, docs = rebuild_vectorstore()
                mensagem = (
                    f"✅ PDF '{filename}' enviado. Base de conhecimento reindexada: "
                    f"{len(docs)} blocos / {index.ntotal} vetores."
                )
            except Exception as e:
                mensagem = f"⚠️ PDF salvo, mas falha ao reindexar: {e}"
        else:
            mensagem = "⚠️ Envie apenas arquivos .pdf"

    return render_template("upload.html", mensagem=mensagem, stats=kb_stats())


@app.route("/admin/retrain")
@login_required
def retrain():
    if not current_user.is_moderator_or_above():
        return "⛔ Acesso negado"

    global index, docs
    try:
        from rag.vectorstore import rebuild_vectorstore
        index, docs = rebuild_vectorstore()
        msg = f"✅ IA reindexada com sucesso! {len(docs)} blocos / {index.ntotal} vetores."
    except Exception as e:
        msg = f"⚠️ Falha ao reindexar: {e}"

    return redirect(url_for("upload", msg=msg))


# ================= ADMIN: GERENCIAR USUÁRIOS =================

@app.route("/admin/usuarios", methods=["GET"])
@login_required
def admin_usuarios():
    if not current_user.is_admin_or_above():
        return "⛔ Acesso negado"

    conn = get_db()
    usuarios = conn.execute("SELECT id, username, role FROM usuarios ORDER BY id ASC").fetchall()
    conn.close()

    gerenciáveis = [u for u in usuarios if current_user.can_manage(u["role"])]

    # Cargos atribuíveis por quem está logado (nunca o próprio nível ou acima).
    if current_user.is_super_admin():
        roles = ["usuario", "moderador", "admin"]
    else:  # admin
        roles = ["usuario", "moderador"]

    return render_template(
        "admin_usuarios.html",
        usuarios=gerenciáveis,
        roles=roles,
        erro=request.args.get("erro"),
        ok=request.args.get("ok"),
    )


@app.route("/admin/usuarios/<int:user_id>/role", methods=["POST"])
@login_required
def alterar_role(user_id):
    if not current_user.is_admin_or_above():
        return jsonify({"erro": "Acesso negado"}), 403

    novo_role = request.form.get("role")
    if novo_role not in ROLE_LEVELS:
        return redirect(url_for("admin_usuarios", erro="Cargo inválido."))

    # super_admin nunca é atribuído pela interface — só via create_admin.py / promover_super_admin.py
    if novo_role == "super_admin":
        return redirect(url_for(
            "admin_usuarios",
            erro="super_admin só pode ser definido via script (create_admin.py / promover_super_admin.py)."
        ))

    conn = get_db()
    alvo = conn.execute("SELECT id, username, role FROM usuarios WHERE id=?", (user_id,)).fetchone()
    if not alvo:
        conn.close()
        return redirect(url_for("admin_usuarios", erro="Usuário não encontrado."))

    # Só gerencia quem está estritamente abaixo (nunca mesmo nível ou acima).
    if not current_user.can_manage(alvo["role"]):
        conn.close()
        return redirect(url_for(
            "admin_usuarios",
            erro="Você só pode gerenciar usuários de nível inferior ao seu."
        ))

    # Só super_admin cria/edita admin.
    if novo_role == "admin" and not current_user.is_super_admin():
        conn.close()
        return redirect(url_for("admin_usuarios", erro="Apenas super_admin pode promover a admin."))

    # Nunca atribuir cargo igual ou superior ao seu.
    if ROLE_LEVELS[novo_role] >= current_user.level():
        conn.close()
        return redirect(url_for(
            "admin_usuarios",
            erro="Não é possível atribuir cargo igual ou superior ao seu."
        ))

    conn.execute("UPDATE usuarios SET role=? WHERE id=?", (novo_role, user_id))
    conn.commit()
    conn.close()
    return redirect(url_for(
        "admin_usuarios",
        ok=f"Cargo de '{alvo['username']}' atualizado para {novo_role}."
    ))


# ================= RUN =================

if __name__ == "__main__":
    # use_reloader=False evita carregar o modelo de embeddings duas vezes
    app.run(debug=True, port=5002, use_reloader=False)
