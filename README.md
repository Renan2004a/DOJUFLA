# DOJUFLA — Assistente Virtual (RAG + LLMs)

Centro Acadêmico de Artes Marciais e Ciências do Esporte — UFLA.

Aplicação web (Flask) que responde perguntas sobre esporte e artes marciais
usando **RAG** (recuperação de contexto em índice vetorial FAISS) e uma LLM
(Ollama local ou Groq na nuvem).

## Requisitos

- Python 3.12
- O `venv/` já vem pronto nesta pasta com todas as dependências
- (Opcional) [Ollama](https://ollama.com) rodando em `localhost:11434` para o modo local

O pipeline de RAG usa **LangChain** (`langchain-community`, `langchain-huggingface`,
`langchain-text-splitters`) com o modelo de embeddings `all-MiniLM-L6-v2`.

## Como rodar

Dentro **desta** pasta:

```powershell
.\venv\Scripts\Activate.ps1
python app.py
```

Ou, sem ativar o venv:

```powershell
& .\venv\Scripts\python.exe app.py
```

Acesse: **http://127.0.0.1:5002**

### Configuração (.env)

Copie `.env.example` para `.env`:

| Variável | Para que serve |
| --- | --- |
| `DOJUFLA_SECRET_KEY` | Chave de sessão do Flask (valor aleatório) |
| `GROQ_API_KEY` | Chave da API Groq (para o modo nuvem) |
| `OLLAMA_URL`, `OLLAMA_MODEL` | Ollama (padrão: local) |
| `EMBED_MODEL`, `RETRIEVE_K`, `CHUNK_SIZE` | Ajustes do RAG (opcionais) |

### No VS Code

**File → Open Folder** → esta pasta → selecione `.\venv\Scripts\python.exe` →
rode com **F5** (há um `.vscode/launch.json`) ou `python app.py`.

## Estrutura

```
app.py                 Application factory e ponto de entrada
config.py              Configuração central (variáveis de ambiente/.env)
extensions.py          Extensões Flask (flask-login)
models.py              Usuário e hierarquia de cargos
database.py            Acesso ao SQLite (schema, migrações, conexões)
blueprints/
  auth.py              Login, cadastro e logout
  chat.py              Chat com streaming, histórico e preferência de LLM
  admin.py             Treinamento da IA e gestão de usuários
rag/
  vectorstore.py       Índice FAISS via LangChain (loaders, splitter, embeddings)
  llm.py               Integração com Ollama e Groq
templates/             Telas (Jinja2)
static/style.css       Estilo institucional
data/base_conhecimento.txt   Texto base indexado
documentos/            PDFs usados na base de conhecimento
tests/                 Testes automatizados (pytest)
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

## "Treinar" a IA com PDF

O envio de PDF **reindexa a base** (RAG), não faz fine-tuning:
o texto é extraído, dividido em blocos, vetorizado e o índice FAISS é
reconstruído. A tela **Treinar IA** mostra a contagem de blocos/vetores/PDFs.

## Testes

```powershell
& .\venv\Scripts\python.exe -m pytest -q
```

## Git

```powershell
git add .
git commit -m "sua mensagem"
git push
```

> `.env` e `database.db` **não** são versionados (veja `.gitignore`).
