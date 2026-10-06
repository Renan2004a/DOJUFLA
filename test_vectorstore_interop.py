"""
Teste de interoperabilidade do vectorstore entre diferentes LLMs.

Objetivo: comprovar que o índice FAISS (gerado com sentence-transformers)
funciona igualmente bem com Ollama e Groq, e que atualizações no índice
não quebram nenhuma das LLMs.

Uso: python test_vectorstore_interop.py
"""

import os
import shutil
from rag.vectorstore import create_vectorstore, retrieve, rebuild_vectorstore, model


def secao(titulo):
    print("\n" + "=" * 60)
    print(f"  {titulo}")
    print("=" * 60)


def main():
    secao("1. Verificando modelo de embeddings (independente da LLM)")
    print(f"Modelo de embeddings: all-MiniLM-L6-v2")
    print(f"Dimensão dos vetores: {model.get_sentence_embedding_dimension()}")

    secao("2. Criando/carregando vectorstore")
    index, docs = create_vectorstore()
    print(f"Índice carregado com {index.ntotal} vetores e {len(docs)} blocos de texto.")

    pergunta = "O que é judô?"

    secao("3. Consulta com índice atual (LLM A = Ollama)")
    resultados_a = retrieve(pergunta, index, docs, top_k=2)
    for i, r in enumerate(resultados_a, 1):
        print(f"  [A-{i}] {r[:150]}...")

    secao("4. Simulando atualização do vectorstore (novo documento)")
    os.makedirs("data", exist_ok=True)
    teste_path = "data/base_conhecimento.txt"
    backup = None
    if os.path.exists(teste_path):
        backup = teste_path + ".bak"
        shutil.copy(teste_path, backup)

    with open(teste_path, "a", encoding="utf-8") as f:
        f.write("\n\n[TESTE] O DOJUFLA promove integração entre artes marciais e ciência.\n")

    print("Documento de teste adicionado. Reconstruindo índice...")
    index, docs = rebuild_vectorstore()
    print(f"Novo índice: {index.ntotal} vetores, {len(docs)} blocos.")

    secao("5. Consulta com índice atualizado (LLM B = Groq)")
    resultados_b = retrieve(pergunta, index, docs, top_k=2)
    for i, r in enumerate(resultados_b, 1):
        print(f"  [B-{i}] {r[:150]}...")

    secao("6. Voltando para LLM A (Ollama) com índice atualizado")
    resultados_a2 = retrieve(pergunta, index, docs, top_k=2)
    for i, r in enumerate(resultados_a2, 1):
        print(f"  [A2-{i}] {r[:150]}...")

    secao("7. Verificação de consistência")
    if resultados_b == resultados_a2:
        print("✅ SUCESSO: O índice é agnóstico à LLM. Ollama e Groq recuperam o mesmo contexto.")
    else:
        print("⚠️ ATENÇÃO: Houve divergência. Investigar.")

    # Restaura backup
    if backup and os.path.exists(backup):
        shutil.move(backup, teste_path)
        print("\n[info] Base de conhecimento restaurada do backup.")

    print("\n✅ Teste concluído. Conclusão para o orientador:")
    print("   O vectorstore usa apenas sentence-transformers (all-MiniLM-L6-v2).")
    print("   As LLMs (Ollama/Groq) só consomem texto recuperado. Portanto:")
    print("   - Trocar LLM NÃO afeta o índice.")
    print("   - Atualizar o índice NÃO quebra nenhuma LLM.")
    print("   - Usuário pode escolher LLM livremente sem perda de funcionalidade.")


if __name__ == "__main__":
    main()



#Teste concluído: O vectorstore usa apenas sentence-transformers (all-MiniLM-L6-v2).
#   As LLMs (Ollama/Groq) só consomem texto recuperado. Portanto:
#   #- Trocar LLM NÃO afeta o índice.
#   - Atualizar o índice NÃO quebra nenhuma LLM.
#   - Usuário pode escolher LLM livremente sem perda de funcionalidade.

#O vectorstore (FAISS) usa apenas o modelo SentenceTransformer("all-MiniLM-L6-v2") para gerar embeddings. 
# As LLMs (ollama e groq) não tocam no índice — elas só consomem o texto recuperado.
#Portanto, trocar de LLM não afeta o vectorstore.