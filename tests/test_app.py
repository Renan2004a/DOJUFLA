"""Testes de ponta a ponta das principais funcionalidades da aplicação."""


def _fake_llm(contexto, pergunta, historico=None, stream=True, llm="ollama"):
    yield "Resposta "
    yield "de teste."


def _sem_vectorstore():
    return None


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
    assert linhas[0]["resposta"] == "Resposta de teste."


def test_conversas_isoladas_por_usuario(client, make_user, login):
    login(make_user("ana"))
    conversa_id = client.post("/conversa/nova").get_json()["conversa_id"]

    login(make_user("bruno"))
    assert client.get(f"/conversa/{conversa_id}").status_code == 404


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


def test_niveis_de_acesso(client, make_user, login):
    login(make_user("user"))
    assert client.get("/admin/usuarios").status_code == 403
    assert client.get("/admin/upload").status_code == 403

    login(make_user("mod", role="moderador"))
    assert client.get("/admin/upload").status_code == 200
    assert client.get("/admin/usuarios").status_code == 403


def test_set_llm_valida_opcao(client, make_user, login, query):
    user_id = make_user("ana")
    login(user_id)

    assert client.post("/set_llm", json={"llm": "groq"}).status_code == 200
    assert query("SELECT llm_preference FROM usuarios WHERE id=?", (user_id,))[0][0] == "groq"

    assert client.post("/set_llm", json={"llm": "inexistente"}).status_code == 400
