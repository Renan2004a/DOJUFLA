from database import get_db, init_db
from werkzeug.security import generate_password_hash

init_db()
conn = get_db()

username = "admin"
password = generate_password_hash("123")
role = "super_admin"

try:
    conn.execute(
        "INSERT INTO usuarios (username, password, role) VALUES (?, ?, ?)",
        (username, password, role)
    )
    conn.commit()
    print("✅ super_admin criado com sucesso!")
except Exception as e:
    print(f"⚠️ Já existe ou erro: {e}")

conn.close()