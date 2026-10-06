import sqlite3
from database import DB_PATH

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

print('=' * 70)
print('CONVERSAS')
print('=' * 70)
for c in conn.execute('SELECT id, user_id, titulo FROM conversas ORDER BY id').fetchall():
    print(f"  id={c['id']} user={c['user_id']} titulo={c['titulo']!r}")

print()
print('=' * 70)
print('HISTORICO (todas as mensagens)')
print('=' * 70)
rows = conn.execute(
    'SELECT id, conversa_id, user_id, substr(pergunta,1,40) as p, substr(resposta,1,40) as r FROM historico ORDER BY id'
).fetchall()
if not rows:
    print("  (VAZIO — nenhuma mensagem foi salva!)")
else:
    for h in rows:
        conv_id = h['conversa_id'] if h['conversa_id'] is not None else 'NULL'
        print(f"  id={h['id']} conversa_id={conv_id} user={h['user_id']}")
        print(f"      P: {h['p']!r}")
        print(f"      R: {h['r']!r}")

print()
print('=' * 70)
print('RESUMO')
print('=' * 70)
total_conv = conn.execute('SELECT COUNT(*) FROM conversas').fetchone()[0]
total_hist = conn.execute('SELECT COUNT(*) FROM historico').fetchone()[0]
orfas = conn.execute('SELECT COUNT(*) FROM historico WHERE conversa_id IS NULL').fetchone()[0]
print(f"  Total de conversas: {total_conv}")
print(f"  Total de mensagens: {total_hist}")
print(f"  Mensagens órfãs (conversa_id NULL): {orfas}")

# Quantas mensagens por conversa
print()
print('Mensagens por conversa:')
for c in conn.execute('SELECT id, titulo FROM conversas ORDER BY id').fetchall():
    n = conn.execute('SELECT COUNT(*) FROM historico WHERE conversa_id=?', (c['id'],)).fetchone()[0]
    print(f"  Conversa {c['id']} ({c['titulo']!r}): {n} mensagem(ns)")

conn.close()