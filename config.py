"""Configuração central da aplicação.

Todos os valores podem ser sobrescritos por variáveis de ambiente ou por um
arquivo ``.env`` na raiz do projeto.
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Carrega o .env (se existir) antes de ler qualquer variável.
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(BASE_DIR, ".env"))
except Exception:  # pragma: no cover - dotenv é opcional
    pass


class Config:
    # ----- Caminhos -----
    BASE_DIR = BASE_DIR
    DATABASE = os.path.join(BASE_DIR, "database.db")
    DOCS_DIR = os.path.join(BASE_DIR, "documentos")
    DATA_FILE = os.path.join(BASE_DIR, "data", "base_conhecimento.txt")
    RAG_DIR = os.path.join(BASE_DIR, "rag")
    INDEX_FILE = os.path.join(RAG_DIR, "index.faiss")
    INDEX_META = os.path.join(RAG_DIR, "meta.json")

    # ----- Flask -----
    SECRET_KEY = os.environ.get("DOJUFLA_SECRET_KEY", "dev-secret-troque-isto")
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_UPLOAD_MB", "40")) * 1024 * 1024

    # ----- Pré-processamento / busca -----
    EMBED_MODEL = os.environ.get("EMBED_MODEL", "all-MiniLM-L6-v2")
    EMBED_BATCH_SIZE = int(os.environ.get("EMBED_BATCH_SIZE", "64"))
    CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "800"))
    CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "150"))
    RETRIEVE_K = int(os.environ.get("RETRIEVE_K", "4"))
    HISTORY_LIMIT = int(os.environ.get("HISTORY_LIMIT", "6"))

    # Extensões aceitas no treinamento da IA.
    ALLOWED_EXTENSIONS = (".pdf", ".txt", ".md", ".docx")

    # ----- LLMs -----
    OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
    OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")

    GROQ_URL = os.environ.get("GROQ_URL", "https://api.groq.com/openai/v1/chat/completions")
    GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
    GROQ_REASONING_EFFORT = os.environ.get("GROQ_REASONING_EFFORT", "low")
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

    GEMINI_URL = os.environ.get("GEMINI_URL", "https://generativelanguage.googleapis.com/v1beta")
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

    LLM_TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "120"))

    # Provedor padrão para novos usuários (precisa estar configurado).
    DEFAULT_LLM = os.environ.get("DEFAULT_LLM", "ollama")

    # ----- Segurança -----
    PASSWORD_MIN_LENGTH = int(os.environ.get("PASSWORD_MIN_LENGTH", "6"))
    LOGIN_MAX_ATTEMPTS = int(os.environ.get("LOGIN_MAX_ATTEMPTS", "5"))
    LOGIN_WINDOW_SECONDS = int(os.environ.get("LOGIN_WINDOW_SECONDS", "300"))
    WTF_CSRF_ENABLED = True
