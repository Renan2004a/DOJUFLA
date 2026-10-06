"""Índice vetorial (RAG) construído com LangChain + FAISS.

Responsabilidades:
- carregar os documentos (texto base + arquivos em ``documentos/``);
- dividir em blocos;
- gerar embeddings (em lotes, reportando progresso) e indexar no FAISS;
- persistir/carregar o índice e reconstruí-lo quando os documentos mudam;
- devolver os trechos recuperados com suas fontes (arquivo e página).
"""
import hashlib
import json
import logging
import os

from langchain_community.document_loaders import (
    Docx2txtLoader,
    PyPDFLoader,
    TextLoader,
)
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import Config

logger = logging.getLogger(__name__)

_vectorstore = None
_embeddings = None


# --------------------------------------------------------------------------- #
# Embeddings
# --------------------------------------------------------------------------- #
def get_embeddings() -> HuggingFaceEmbeddings:
    """Instancia (uma vez) o modelo de embeddings."""
    global _embeddings
    if _embeddings is None:
        logger.info("Carregando modelo de embeddings: %s", Config.EMBED_MODEL)
        _embeddings = HuggingFaceEmbeddings(
            model_name=Config.EMBED_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    return _embeddings


# --------------------------------------------------------------------------- #
# Documentos
# --------------------------------------------------------------------------- #
def _document_files() -> list:
    """Caminhos dos arquivos suportados na pasta de documentos."""
    if not os.path.isdir(Config.DOCS_DIR):
        return []
    return [
        os.path.join(Config.DOCS_DIR, name)
        for name in sorted(os.listdir(Config.DOCS_DIR))
        if name.lower().endswith(Config.ALLOWED_EXTENSIONS)
    ]


def _load_file(path: str) -> list:
    ext = os.path.splitext(path)[1].lower()
    logger.info("Carregando arquivo: %s", os.path.basename(path))
    if ext == ".pdf":
        return PyPDFLoader(path).load()
    if ext == ".docx":
        return Docx2txtLoader(path).load()
    return TextLoader(path, encoding="utf-8").load()


def load_documents() -> list:
    """Carrega o texto base e todos os arquivos suportados da pasta."""
    documents = []
    if os.path.exists(Config.DATA_FILE):
        documents.extend(TextLoader(Config.DATA_FILE, encoding="utf-8").load())
    for path in _document_files():
        try:
            documents.extend(_load_file(path))
        except Exception:  # noqa: BLE001 - um arquivo ruim não derruba o resto
            logger.exception("Falha ao ler %s", os.path.basename(path))
    return documents


def split_documents(documents: list) -> list:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=Config.CHUNK_SIZE,
        chunk_overlap=Config.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_documents(documents)


def _fingerprint() -> str:
    """Assinatura do conteúdo dos documentos (estável entre clones do Git)."""
    digest = hashlib.md5()
    if os.path.exists(Config.DATA_FILE):
        with open(Config.DATA_FILE, "rb") as handle:
            digest.update(handle.read())
    for path in _document_files():
        digest.update(os.path.basename(path).encode("utf-8"))
        with open(path, "rb") as handle:
            digest.update(handle.read())
    return digest.hexdigest()


# --------------------------------------------------------------------------- #
# Índice
# --------------------------------------------------------------------------- #
def _saved_meta() -> dict:
    if os.path.exists(Config.INDEX_META):
        try:
            with open(Config.INDEX_META, encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError):
            logger.warning("meta.json inválido; o índice será reconstruído.")
    return {}


def _save_meta(blocks: int) -> None:
    with open(Config.INDEX_META, "w", encoding="utf-8") as handle:
        json.dump({"fingerprint": _fingerprint(), "blocos": blocks}, handle)


def build_index(progress=None) -> FAISS:
    """Constrói o índice do zero, reportando progresso opcional.

    ``progress`` é chamado como ``progress(done, total)`` a cada lote embedado.
    """
    global _vectorstore

    documents = split_documents(load_documents())
    if not documents:
        raise ValueError("Nenhum documento encontrado para indexação.")

    embeddings = get_embeddings()
    texts = [doc.page_content for doc in documents]
    metadatas = [doc.metadata for doc in documents]
    total = len(texts)
    batch_size = max(1, Config.EMBED_BATCH_SIZE)

    logger.info("Indexando %d blocos (lotes de %d)...", total, batch_size)
    vectors = []
    for start in range(0, total, batch_size):
        batch = texts[start : start + batch_size]
        vectors.extend(embeddings.embed_documents(batch))
        if progress:
            progress(min(start + len(batch), total), total)

    pairs = list(zip(texts, vectors))
    _vectorstore = FAISS.from_embeddings(pairs, embeddings, metadatas=metadatas)

    os.makedirs(Config.RAG_DIR, exist_ok=True)
    _vectorstore.save_local(Config.RAG_DIR)
    _save_meta(total)
    logger.info("Índice salvo com %d vetores.", _vectorstore.index.ntotal)
    return _vectorstore


# Mantém o nome usado pelo admin.
rebuild_vectorstore = build_index


def load_vectorstore() -> FAISS:
    """Carrega o índice salvo; reconstrói se estiver ausente/desatualizado."""
    global _vectorstore
    if _vectorstore is not None:
        return _vectorstore

    up_to_date = (
        os.path.exists(Config.INDEX_FILE)
        and _saved_meta().get("fingerprint") == _fingerprint()
    )
    if up_to_date:
        logger.info("Carregando índice FAISS salvo...")
        _vectorstore = FAISS.load_local(
            Config.RAG_DIR,
            get_embeddings(),
            allow_dangerous_deserialization=True,
        )
    else:
        logger.info("Índice ausente/desatualizado. Reconstruindo...")
        build_index()
    return _vectorstore


def get_vectorstore():
    """Retorna o índice ou ``None`` se não for possível carregá-lo."""
    try:
        return load_vectorstore()
    except Exception:  # pragma: no cover - depende de arquivos externos
        logger.exception("Falha ao carregar o vectorstore.")
        return None


# --------------------------------------------------------------------------- #
# Busca
# --------------------------------------------------------------------------- #
def retrieve_with_sources(query: str, vectorstore=None, k: int = None) -> list:
    """Retorna trechos com a fonte (arquivo e página) de cada um."""
    if vectorstore is None:
        return []
    k = k or Config.RETRIEVE_K
    results = []
    for doc in vectorstore.similarity_search(query, k=k):
        metadata = doc.metadata or {}
        source = metadata.get("source") or ""
        page = metadata.get("page")
        results.append({
            "texto": doc.page_content,
            "arquivo": os.path.basename(source) if source else "base de conhecimento",
            "pagina": (page + 1) if isinstance(page, int) else None,
        })
    return results


def retrieve(query: str, vectorstore=None, k: int = None) -> list:
    """Retorna apenas os textos dos ``k`` blocos mais similares."""
    return [item["texto"] for item in retrieve_with_sources(query, vectorstore, k)]


def stats() -> dict:
    """Resumo da base para a tela de treinamento."""
    blocks = _saved_meta().get("blocos", 0)
    vectors = _vectorstore.index.ntotal if _vectorstore is not None else blocks
    return {
        "modelo": Config.EMBED_MODEL,
        "blocos": blocks,
        "vetores": vectors,
        "arquivos": len(_document_files()),
    }
