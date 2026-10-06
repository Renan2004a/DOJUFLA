"""
Script para promover um usuário existente a super_admin.
Uso: python promover_super_admin.py <username>
"""
import sys
from database import get_db, init_db
from werkzeug.security import generate_password_hash

init_db()

if len(sys.argv) < 2:
    print("Uso: python promover_super_admin.py <username>")
    sys.exit(1)

username = sys.argv[1]
conn = get_db()

user = conn.execute("SELECT id, username, role FROM usuarios WHERE username=?", (username,)).fetchone()

if user:
    conn.execute("UPDATE usuarios SET role='super_admin' WHERE id=?", (user["id"],))
    conn.commit()
    print(f"✅ '{username}' promovido a super_admin.")
else:
    # Se não existir, cria
    senha = generate_password_hash("123")
    conn.execute(
        "INSERT INTO usuarios (username, password, role) VALUES (?, ?, 'super_admin')",
        (username, senha)
    )
    conn.commit()
    print(f"✅ super_admin '{username}' criado com senha padrão '123'.")

conn.close()