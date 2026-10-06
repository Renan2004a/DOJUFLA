"""Teste rápido da LLM: faz uma pergunta e imprime a resposta (streaming).

Uso: python testar_ia.py
Requer o Ollama em execução (ou configure GROQ_API_KEY e mude a LLM abaixo).
"""
from rag.llm import gerar_resposta
from rag.vectorstore import load_vectorstore, retrieve

PERGUNTA = "O que é judô?"

print("Carregando índice vetorial...")
vectorstore = load_vectorstore()
print(f"OK: {vectorstore.index.ntotal} vetores\n")

contexto = "\n".join(retrieve(PERGUNTA, vectorstore))
print(f"Blocos recuperados: {len(contexto)} caracteres\n")
print("=" * 60)
print("RESPOSTA DA IA (Ollama):")
print("=" * 60)

try:
    for token in gerar_resposta(contexto, PERGUNTA, stream=True, llm="ollama"):
        print(token, end="", flush=True)
    print("\n\n✅ IA respondeu com sucesso")
except Exception as exc:  # noqa: BLE001
    print(f"\n\n❌ ERRO: {exc}")
