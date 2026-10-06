# DOJUFLA — Assistente Virtual (RAG + LLMs)

Centro Acadêmico de Artes Marciais e Ciências do Esporte — UFLA.

Aplicação web (Flask) que responde perguntas sobre esporte e artes marciais
usando **RAG** (busca semântica no índice FAISS) e uma LLM (Ollama local ou Groq).

## Requisitos

- Python 3.12
- O `venv/` já vem pronto nesta pasta com todas as dependências
- (Opcional) [Ollama](https://ollama.com) rodando em `localhost:11434` para o modo local

Os embeddings usam **fastembed** (ONNX, `BAAI/bge-small-en-v1.5`) — leve e sem GPU.

## Como rodar localmente

No terminal, dentro **desta** pasta:

```powershell
.\venv\Scripts\Activate.ps1
python app.py
```

Ou, sem ativar o venv:

```powershell
& .\venv\Scripts\python.exe app.py
```

Depois acesse: **http://127.0.0.1:5002**

### Configuração (.env)

Copie `.env.example` para `.env` e preencha:

| Variável | Para que serve |
| --- | --- |
| `DOJUFLA_SECRET_KEY` | Chave de sessão do Flask (aleatória) |
| `GROQ_API_KEY` | Chave da API Groq (nuvem) |
| `DEFAULT_LLM` | LLM padrão de novos usuários: `ollama` ou `groq` |
| `SUPERADMIN_USER` / `SUPERADMIN_PASSWORD` | Criam/garantem um super_admin no start |
| `OLLAMA_URL`, `OLLAMA_MODEL` | Opcionais (padrão local) |

### No VS Code

1. **File → Open Folder** → selecione esta pasta
2. Selecione o interpretador `.\venv\Scripts\python.exe`
3. Rode com **F5** (já existe `.vscode/launch.json`) ou `python app.py`

## Estrutura

```
app.py                 Rotas Flask (chat, histórico, admin)
database.py            SQLite + migrações
rag/vectorstore.py     Índice FAISS + embeddings (fastembed/ONNX)
rag/llm.py             Integração Ollama / Groq
templates/             Telas (Jinja2)
static/style.css       Estilo institucional
data/base_conhecimento.txt   Texto base indexado
documentos/            PDFs usados na base de conhecimento
database.db            Banco de dados (não versionado)
create_admin.py                 Cria um super_admin (via script)
promover_super_admin.py         Promove usuário a super_admin (via script)
diagnostico.py                  Inspeção do banco (dev)
testar_ia.py                    Teste rápido da LLM (dev)
render.yaml                     Blueprint de deploy no Render
```

## Hierarquia de cargos

`super_admin > admin > moderador > usuario`

- Cada um gerencia **apenas** quem está estritamente abaixo.
- `/register` sempre cria `usuario`.
- **Moderador+**: treinar IA. **Admin+**: gerenciar usuários.
- **super_admin** só é definido por script (`promover_super_admin.py`) ou pelas
  variáveis `SUPERADMIN_USER`/`SUPERADMIN_PASSWORD` no start.

## "Treinar" a IA com PDF

O envio de PDF **reindexa a base** (RAG), não faz fine-tuning:
o texto é extraído, vetorizado e o índice FAISS é reconstruído.
A tela **Treinar IA** mostra a contagem de blocos/vetores/PDFs para conferência.

## Deploy no Render

O repositório inclui `render.yaml`. Para subir:

1. Suba o projeto para o GitHub (veja abaixo).
2. No Render: **New → Blueprint** → selecione o repositório.
3. O Render lê o `render.yaml` e pede os valores marcados com `sync: false`:
   - `GROQ_API_KEY` — sua chave da Groq
   - `SUPERADMIN_PASSWORD` — senha do admin inicial
4. Acesse a URL gerada (ex.: `https://dojufla.onrender.com`).

Observações:

- No plano **free** o serviço hiberna após 15 min de inatividade e o disco é
  **efêmero** (o SQLite é recriado a cada deploy/restart — o super_admin é
  recriado automaticamente pelas variáveis acima).
- Não há Ollama no Render: use `DEFAULT_LLM=groq`.
- Health check em `/healthz`.

## GitHub

```powershell
git init
git add .
git commit -m "DOJUFLA: chat com RAG, histórico e hierarquia"
git branch -M main
git remote add origin https://github.com/<SEU_USUARIO>/<SEU_REPO>.git
git push -u origin main
```

> O `.env` e o `database.db` **não** são versionados (veja `.gitignore`).
