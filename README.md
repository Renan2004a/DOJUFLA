# DOJUFLA — Assistente Virtual (RAG + LLMs)

Centro Acadêmico de Artes Marciais e Ciências do Esporte — UFLA.

Aplicação web (Flask) que responde perguntas sobre esporte e artes marciais
usando **RAG** (recuperação de contexto em índice vetorial FAISS) e uma LLM
(Ollama local, Groq ou Google Gemini).

## Requisitos

- Python 3.12
- O `venv/` já vem pronto nesta pasta com todas as dependências
- (Opcional) [Ollama](https://ollama.com) rodando em `localhost:11434` para o modo local

O pipeline de RAG usa **LangChain** (`langchain-community`, `langchain-huggingface`,
`langchain-text-splitters`) com o modelo de embeddings `all-MiniLM-L6-v2`.

## Como rodar

```powershell
.\venv\Scripts\Activate.ps1
python app.py
```

Ou, sem ativar o venv:

```powershell
& .\venv\Scripts\python.exe app.py
```

Acesse **http://127.0.0.1:5002**. No VS Code: **F5** (há um `.vscode/launch.json`).

## Configuração (.env)

Copie `.env.example` para `.env`:

| Variável | Para que serve |
| --- | --- |
| `DOJUFLA_SECRET_KEY` | Chave de sessão do Flask (valor aleatório) |
| `GROQ_API_KEY` | Habilita o provedor **Groq** |
| `GEMINI_API_KEY` | Habilita o provedor **Google Gemini** |
| `DEFAULT_LLM` | Provedor padrão de novos usuários (`ollama`/`groq`/`gemini`) |
| `OLLAMA_URL`, `OLLAMA_MODEL` | Ollama (padrão local) |
| `EMBED_MODEL`, `RETRIEVE_K`, `CHUNK_SIZE`, `PASSWORD_MIN_LENGTH` | Ajustes (opcionais) |

## Provedores de LLM

Os provedores aparecem na tela automaticamente **quando a chave está configurada**.
Para habilitar o Gemini, basta preencher `GEMINI_API_KEY` no `.env` e reiniciar — a
opção "Google Gemini Flash" surge no seletor.

Para adicionar um provedor novo (ex.: outro modelo pago), basta implementar uma
função de streaming e registrá-la em `rag/llm.py`:

```python
def _meu_provedor_stream(prompt):
    ...  # yields de texto

PROVIDERS["meu_provedor"] = {
    "label": "Meu Provedor",
    "stream": _meu_provedor_stream,
    "key_attr": "MEU_PROVEDOR_API_KEY",  # None se não precisar de chave
}
```

## Estrutura

```
app.py                 Application factory e ponto de entrada
config.py              Configuração central (variáveis de ambiente/.env)
extensions.py          Extensões Flask (flask-login, CSRF)
models.py              Usuário e hierarquia de cargos
database.py            Acesso ao SQLite (schema, migrações, conexões)
blueprints/
  auth.py              Login (com limite de tentativas), cadastro, conta, logout
  chat.py              Chat com streaming, histórico, fontes, exportar
  admin.py             Treinamento da IA (upload/reindex) e gestão de usuários
rag/
  vectorstore.py       Índice FAISS via LangChain (loaders, splitter, embeddings)
  indexer.py           Reindexação em segundo plano (com progresso)
  llm.py               Provedores de LLM (Ollama, Groq, Gemini)
templates/             Telas (Jinja2)
static/style.css       Estilo institucional
data/base_conhecimento.txt   Texto base indexado
documentos/            Arquivos usados na base (PDF, TXT, MD, DOCX)
tests/                 Testes automatizados (pytest)
.github/workflows/     CI (roda os testes a cada push)
create_admin.py        Cria um super_admin (via script)
promover_super_admin.py   Promove usuário a super_admin (via script)
diagnostico.py         Inspeção do banco (dev)
testar_ia.py           Teste rápido da LLM (dev)
```

## Hierarquia de cargos

`super_admin > admin > moderador > usuario`

- Cada um gerencia **apenas** quem está estritamente abaixo.
- `/register` sempre cria `usuario`.
- **Moderador+**: treinar IA. **Admin+**: gerenciar usuários.
- **super_admin** só é definido por script: `python promover_super_admin.py <usuario>`

## Treinar a IA

Envie arquivos **PDF, TXT, MD ou DOCX** (vários de uma vez). O texto é extraído,
dividido em blocos e indexado. A reindexação roda **em segundo plano**, com
progresso na própria tela. As respostas mostram as **fontes** (arquivo e página).

## Conta

Cada usuário pode trocar a própria senha em **Conta** (no menu).

## Testes

```powershell
& .\venv\Scripts\python.exe -m pytest -q
```

O GitHub Actions roda os testes automaticamente a cada push (`.github/workflows/tests.yml`).

## Git

```powershell
git add .
git commit -m "sua mensagem"
git push
```

> `.env` e `database.db` **não** são versionados (veja `.gitignore`).
