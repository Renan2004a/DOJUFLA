"""Camada de acesso ao banco de dados (SQLite) e migrações."""
import sqlite3
from contextlib import contextmanager

from flask import current_app, has_app_context

from config import Config

# Compatibilidade com scripts antigos (create_admin.py, diagnostico.py...).
DB_PATH = Config.DATABASE

_SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    username       TEXT UNIQUE NOT NULL,
    password       TEXT NOT NULL,
    role           TEXT DEFAULT 'usuario',
    llm_preference TEXT DEFAULT 'ollama'
);

CREATE TABLE IF NOT EXISTS conversas (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    titulo     TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES usuarios (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS historico (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    conversa_id INTEGER,
    user_id     INTEGER NOT NULL,
    pergunta    TEXT NOT NULL,
    resposta    TEXT NOT NULL,
    timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversa_id) REFERENCES conversas (id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES usuarios (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_conversas_user    ON conversas (user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_historico_conversa ON historico (conversa_id, id);
"""

# Colunas adicionadas ao longo do tempo (bancos antigos).
_MIGRATIONS = {
    "usuarios": {"role": "TEXT DEFAULT 'usuario'",
                 "llm_preference": "TEXT DEFAULT 'ollama'"},
    "conversas": {"updated_at": "TIMESTAMP"},
    "historico": {"conversa_id": "INTEGER", "timestamp": "TIMESTAMP", "fontes": "TEXT"},
}


def db_path() -> str:
    """Caminho do banco: usa o da app (testes) ou o padrão do projeto."""
    if has_app_context():
        return current_app.config["DATABASE"]
    return Config.DATABASE


def get_db() -> sqlite3.Connection:
    """Abre uma conexão SQLite configurada (Row factory + foreign keys)."""
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db():
    """Context manager: abre, faz commit (ou rollback) e fecha a conexão."""
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _columns(cursor, table: str):
    return [row[1] for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()]


def _migrate(cursor) -> None:
    for table, columns in _MIGRATIONS.items():
        existing = _columns(cursor, table)
        for column, definition in columns.items():
            if column not in existing:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db() -> None:
    """Cria as tabelas (se necessário) e aplica migrações simples."""
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.executescript(_SCHEMA)
        _migrate(cursor)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Banco inicializado em {db_path()}")
