import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # ===== TABELAS =====
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'usuario',
            llm_preference TEXT DEFAULT 'ollama'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            titulo TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES usuarios (id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversa_id INTEGER,
            user_id INTEGER NOT NULL,
            pergunta TEXT NOT NULL,
            resposta TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversa_id) REFERENCES conversas (id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES usuarios (id) ON DELETE CASCADE
        )
    """)

    # ===== MIGRAÇÕES (adicionam colunas em bancos antigos) =====
    def colunas(tabela):
        return [r[1] for r in cursor.execute(f"PRAGMA table_info({tabela})").fetchall()]

    # usuarios
    cols = colunas("usuarios")
    if "role" not in cols:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN role TEXT DEFAULT 'usuario'")
        print("🔧 +usuarios.role")
    if "llm_preference" not in cols:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN llm_preference TEXT DEFAULT 'ollama'")
        print("🔧 +usuarios.llm_preference")

    # conversas
    cols = colunas("conversas")
    if "updated_at" not in cols:
        cursor.execute("ALTER TABLE conversas ADD COLUMN updated_at TIMESTAMP")
        print("🔧 +conversas.updated_at")

    # historico
    cols = colunas("historico")
    if "conversa_id" not in cols:
        cursor.execute("ALTER TABLE historico ADD COLUMN conversa_id INTEGER")
        print("🔧 +historico.conversa_id")
    if "timestamp" not in cols:
        cursor.execute("ALTER TABLE historico ADD COLUMN timestamp TIMESTAMP")
        print("🔧 +historico.timestamp")

    # copia data -> timestamp se necessário
    if "data" in cols and "timestamp" not in cols:
        try:
            cursor.execute("UPDATE historico SET timestamp = data WHERE timestamp IS NULL")
            print("🔧 dados migrados data -> timestamp")
        except Exception as e:
            print(f"[aviso] migração data -> timestamp: {e}")

    conn.commit()

    # ===== CONFIRMAÇÃO =====
    print("=" * 60)
    print("📋 ESTRUTURA DO BANCO")
    print("  historico:", colunas("historico"))
    print("  conversas:", colunas("conversas"))
    print("  usuarios :", colunas("usuarios"))
    if "conversa_id" in colunas("historico"):
        print("  ✅ conversa_id presente")
    else:
        print("  ❌ conversa_id AUSENTE — algo está errado!")
    print("=" * 60)

    conn.close()

if __name__ == "__main__":
    init_db()
    print("✅ Banco de dados inicializado com sucesso!")