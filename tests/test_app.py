"""Testes de ponta a ponta das principais funcionalidades da aplicação."""
import json

from langchain_core.documents import Document


def _fake_llm(contexto, pergunta, historico=None, stream=True, llm="ollama"):
    yield "Resposta "
    yield "de teste."


def _sem_vectorstore():
    return None


class _FakeVectorStore:
    """Vectorstore mínimo usado para testar as fontes."""

    def __init__(self, documents):
        self._documents = documents

    def similarity_search(self, query, k=4):
        return self._documents[:k]


# --------------------------------------------------------------------------- #
# Autenticação / acesso
# --------------------------------------------------------------------------- #
def test_login_obrigatorio(client):
    resposta = client.get("/")
    assert resposta.status_code == 302
    assert "/login" in resposta.headers["Location"]


def test_cadastro_cria_usuario_comum(client, query):
    resposta = client.post(
        "/login",
        data={"acao": "register", "username": "novo", "password": "senha123"},
        follow_redirects=True,
    )
    assert resposta.status_code == 200
    linhas = query("SELECT role FROM usuarios WHERE username=?", ("novo",))
    assert len(linhas) == 1
    assert linhas[0]["role"] == "usuario"


def test_cadastro_rejeita_senha_curta(client):
    resposta = client.post(
        "/login",
        data={"acao": "register", "username": "curto", "password": "123"},
    )
    assert "ao menos" in resposta.get_data(as_text=True)


def test_niveis_de_acesso(client, make_user, login):
    login(make_user("user"))
    assert client.get("/admin/usuarios").status_code == 403
    assert client.get("/admin/upload").status_code == 403

    login(make_user("mod", role="moderador"))
    assert client.get("/admin/upload").status_code == 200
    assert client.get("/admin/usuarios").status_code == 403


# --------------------------------------------------------------------------- #
# Chat / histórico / fontes
# --------------------------------------------------------------------------- #
def test_historico_persiste_apos_streaming(client, make_user, login, query, monkeypatch):
    monkeypatch.setattr("blueprints.chat.get_vectorstore", _sem_vectorstore)
    monkeypatch.setattr("blueprints.chat.gerar_resposta", _fake_llm)

    login(make_user("ana"))
    resposta = client.post("/ask", json={"question": "O que é judô?", "conversa_id": None})

    assert resposta.status_code == 200
    assert resposta.get_data(as_text=True) == "Resposta de teste."

    conversa_id = int(resposta.headers["X-Conversa-ID"])
    linhas = query(
        "SELECT pergunta, resposta FROM historico WHERE conversa_id=?", (conversa_id,)
    )
    assert len(linhas) == 1
    assert linhas[0]["pergunta"] == "O que é judô?"


def test_fontes_salvas_e_exportadas(client, make_user, login, query, monkeypatch):
    documentos = [
        Document(page_content="O judô foi criado por Jigoro Kano.",
                 metadata={"source": "C:\\docs\\judo.pdf", "page": 2}),
    ]
    monkeypatch.setattr("blueprints.chat.get_vectorstore", lambda: _FakeVectorStore(documentos))
    monkeypatch.setattr("blueprints.chat.gerar_resposta", _fake_llm)

    login(make_user("ana"))
    resposta = client.post("/ask", json={"question": "Quem criou o judô?", "conversa_id": None})
    conversa_id = int(resposta.headers["X-Conversa-ID"])

    fontes = json.loads(resposta.headers["X-Sources"])
    assert fontes == [{"arquivo": "judo.pdf", "pagina": 3}]

    # Consome o streaming (é o que dispara o salvamento no histórico).
    assert resposta.get_data(as_text=True) == "Resposta de teste."

    exportado = client.get(f"/conversa/{conversa_id}/exportar").get_data(as_text=True)
    assert "# " in exportado
    assert "judo.pdf (p. 3)" in exportado


def test_conversas_isoladas_por_usuario(client, make_user, login):
    login(make_user("ana"))
    conversa_id = client.post("/conversa/nova").get_json()["conversa_id"]

    login(make_user("bruno"))
    assert client.get(f"/conversa/{conversa_id}").status_code == 404


def test_renomear_conversa(client, make_user, login):
    login(make_user("ana"))
    conversa_id = client.post("/conversa/nova").get_json()["conversa_id"]

    resposta = client.post(f"/conversa/{conversa_id}/renomear", json={"titulo": "Judô olímpico"})
    assert resposta.status_code == 200

    conversas = client.get("/conversas").get_json()
    assert conversas[0]["titulo"] == "Judô olímpico"


# --------------------------------------------------------------------------- #
# Provedores de LLM
# --------------------------------------------------------------------------- #
def test_provedores_disponiveis_seguem_a_config(client, make_user, login):
    login(make_user("ana"))

    # groq tem chave de teste; gemini está vazio.
    html = client.get("/").get_data(as_text=True)
    assert 'value="groq"' in html
    assert 'value="gemini"' not in html

    assert client.post("/set_llm", json={"llm": "groq"}).status_code == 200
    assert client.post("/set_llm", json={"llm": "gemini"}).status_code == 400


# --------------------------------------------------------------------------- #
# Conta
# --------------------------------------------------------------------------- #
def test_alterar_senha(client, make_user, login):
    login(make_user("ana", password="senha123"))

    assert "incorreta" in client.post(
        "/conta/senha", data={"atual": "errada", "nova": "novasenha"}
    ).get_data(as_text=True)

    assert "alterada com sucesso" in client.post(
        "/conta/senha", data={"atual": "senha123", "nova": "novasenha"}
    ).get_data(as_text=True)


# --------------------------------------------------------------------------- #
# Hierarquia
# --------------------------------------------------------------------------- #
def test_admin_nao_promove_para_admin_nem_super_admin(client, make_user, login, query):
    login(make_user("chefe", role="admin"))
    alvo = make_user("diego", role="usuario")

    client.post(f"/admin/usuarios/{alvo}/role", data={"role": "admin"})
    client.post(f"/admin/usuarios/{alvo}/role", data={"role": "super_admin"})
    assert query("SELECT role FROM usuarios WHERE id=?", (alvo,))[0]["role"] == "usuario"

    client.post(f"/admin/usuarios/{alvo}/role", data={"role": "moderador"})
    assert query("SELECT role FROM usuarios WHERE id=?", (alvo,))[0]["role"] == "moderador"


def test_super_admin_pode_promover_a_admin(client, make_user, login, query):
    login(make_user("root", role="super_admin"))
    alvo = make_user("diego", role="usuario")

    client.post(f"/admin/usuarios/{alvo}/role", data={"role": "admin"})
    assert query("SELECT role FROM usuarios WHERE id=?", (alvo,))[0]["role"] == "admin"


# --------------------------------------------------------------------------- #
# Upload
# --------------------------------------------------------------------------- #
def test_upload_salva_arquivo_e_inicia_reindexacao(app, client, make_user, login, tmp_path, monkeypatch):
    monkeypatch.setattr("blueprints.admin.indexer.start", lambda: True)
    monkeypatch.setattr("config.Config.DOCS_DIR", str(tmp_path / "documentos"))
    monkeypatch.setattr("blueprints.admin.Config.DOCS_DIR", str(tmp_path / "documentos"))
    monkeypatch.setattr("rag.vectorstore.Config.DOCS_DIR", str(tmp_path / "documentos"))

    login(make_user("mod", role="moderador"))
    resposta = client.post(
        "/admin/upload",
        data={"file": (open(__file__, "rb"), "resumo.txt")},
        content_type="multipart/form-data",
    )
    assert resposta.status_code == 200
    assert (tmp_path / "documentos" / "resumo.txt").exists()


def test_upload_rejeita_formato_invalido(client, make_user, login, monkeypatch):
    monkeypatch.setattr("blueprints.admin.indexer.start", lambda: True)
    login(make_user("mod", role="moderador"))
    resposta = client.post(
        "/admin/upload",
        data={"file": (open(__file__, "rb"), "malicioso.exe")},
        content_type="multipart/form-data",
    )
    assert "não aceitos" in resposta.get_data(as_text=True)
