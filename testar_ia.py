from rag.vectorstore import create_vectorstore, retrieve
from rag.llm import gerar_resposta

print("Carregando vectorstore...")
idx, docs = create_vectorstore()
print(f"OK: {idx.ntotal} vetores, {len(docs)} blocos\n")

print("Recuperando contexto...")
ctx = retrieve('o que é judô?', idx, docs)
print(f"Blocos recuperados: {len(ctx)}\n")

print("=" * 60)
print("RESPOSTA DA IA (Ollama):")
print("=" * 60)

try:
    for token in gerar_resposta('\n'.join(ctx), 'o que é judô?', stream=True, llm='ollama'):
        print(token, end='', flush=True)
    print("\n\n✅ IA respondeu com sucesso")
except Exception as e:
    print(f"\n\n❌ ERRO: {e}")