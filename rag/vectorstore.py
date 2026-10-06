import os
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from pypdf import PdfReader


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAG_DIR = os.path.join(BASE_DIR, "rag")

DATA_PATH = os.path.join(BASE_DIR, "data", "base_conhecimento.txt")
DOCS_FOLDER = os.path.join(BASE_DIR, "documentos")
INDEX_PATH = os.path.join(RAG_DIR, "index.faiss")
DOCS_PATH = os.path.join(RAG_DIR, "docs.npy")
META_PATH = os.path.join(RAG_DIR, "meta.npy")

model = SentenceTransformer("all-MiniLM-L6-v2")


def dividir_em_blocos(texto, tamanho=800, sobreposicao=150):
    blocos = []
    passo = tamanho - sobreposicao
    for i in range(0, len(texto), passo):
        bloco = texto[i:i+tamanho]
        if bloco.strip():
            blocos.append(bloco.strip())
    return blocos


def extrair_texto_pdf(caminho):
    reader = PdfReader(caminho)
    texto = ""
    for pagina in reader.pages:
        conteudo = pagina.extract_text()
        if conteudo:
            texto += conteudo + "\n"
    return texto


def load_txt_documents():
    docs = []
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            docs.extend(dividir_em_blocos(f.read()))
    return docs


def load_pdf_documents():
    docs = []
    if not os.path.exists(DOCS_FOLDER):
        return docs
    for arquivo in os.listdir(DOCS_FOLDER):
        if arquivo.lower().endswith(".pdf"):
            caminho = os.path.join(DOCS_FOLDER, arquivo)
            print(f"Carregando PDF: {arquivo}")
            docs.extend(dividir_em_blocos(extrair_texto_pdf(caminho)))
    return docs


def _fingerprint_docs():
    """Assinatura baseada no CONTEÚDO dos documentos (estável entre clones/git)."""
    import hashlib
    h = hashlib.md5()
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "rb") as f:
            h.update(f.read())
    if os.path.exists(DOCS_FOLDER):
        for arq in sorted(os.listdir(DOCS_FOLDER)):
            if arq.lower().endswith(".pdf"):
                h.update(arq.encode())
                with open(os.path.join(DOCS_FOLDER, arq), "rb") as f:
                    h.update(f.read())
    return h.hexdigest()


def rebuild_vectorstore():
    """Força a reconstrução do índice FAISS do zero."""
    print("🔨 Reconstruindo índice vetorial do zero...")

    docs = []
    docs.extend(load_txt_documents())
    docs.extend(load_pdf_documents())

    if not docs:
        raise ValueError("Nenhum documento encontrado para indexação.")

    print(f"Total de blocos carregados: {len(docs)}")

    embeddings = model.encode(docs, convert_to_numpy=True, show_progress_bar=True)
    dimension = embeddings.shape[1]

    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)

    os.makedirs(RAG_DIR, exist_ok=True)
    faiss.write_index(index, INDEX_PATH)
    np.save(DOCS_PATH, np.array(docs, dtype=object))
    np.save(META_PATH, np.array([_fingerprint_docs()], dtype=object))

    print("✅ Índice FAISS reconstruído e salvo.")
    return index, docs


def create_vectorstore():
    """Carrega o índice salvo, mas reconstrói se os documentos mudaram."""
    if os.path.exists(INDEX_PATH) and os.path.exists(DOCS_PATH):
        # Verifica se os documentos mudaram desde a última indexação
        try:
            if os.path.exists(META_PATH):
                meta_salva = np.load(META_PATH, allow_pickle=True)[0]
                if meta_salva != _fingerprint_docs():
                    print("⚠️ Documentos alterados detectados. Reconstruindo índice...")
                    return rebuild_vectorstore()
        except Exception as e:
            print(f"[aviso] Não foi possível verificar fingerprint: {e}")

        print("Carregando índice FAISS salvo...")
        index = faiss.read_index(INDEX_PATH)
        docs = np.load(DOCS_PATH, allow_pickle=True).tolist()
        return index, docs

    return rebuild_vectorstore()


def retrieve(query, index, docs, top_k=4):
    query_embedding = model.encode([query], convert_to_numpy=True)
    distances, indices = index.search(query_embedding, top_k)
    resultados = []
    for i in indices[0]:
        if 0 <= i < len(docs):
            resultados.append(docs[i])
    return resultados