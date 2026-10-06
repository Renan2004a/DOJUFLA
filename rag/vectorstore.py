"""Índice vetorial (RAG) construído com LangChain + FAISS.

Responsabilidades:
- carregar os documentos (texto base + PDFs);
- dividir em blocos;
- gerar embeddings e indexar no FAISS;
- persistir/carregar o índice e reconstruí-lo quando os documentos mudam.
"""
import hashlib
import json
import logging
import os

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import Config

logger = logging.getLogger(__name__)

# Cache em memória do índice carregado.
_vectorstore = None
_embeddings = None


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


def _fingerprint() -> str:
    """Assinatura do conteúdo dos documentos (estável entre clones do Git)."""
    digest = hashlib.md5()
    if os.path.exists(Config.DATA_FILE):
        with open(Config.DATA_FILE, "rb") as handle:
            digest.update(handle.read())
    if os.path.isdir(Config.DOCS_DIR):
        for name in sorted(os.listdir(Config.DOCS_DIR)):
            if name.lower().endswith(".pdf"):
                digest.update(name.encode("utf-8"))
                with open(os.path.join(Config.DOCS_DIR, name), "rb") as handle:
                    digest.update(handle.read())
    return digest.hexdigest()


def _load_documents() -> list:
    documents = []
    if os.path.exists(Config.DATA_FILE):
        documents.extend(TextLoader(Config.DATA_FILE, encoding="utf-8").load())
    if os.path.isdir(Config.DOCS_DIR):
        for name in sorted(os.listdir(Config.DOCS_DIR)):
            if name.lower().endswith(".pdf"):
                logger.info("Carregando PDF: %s", name)
                documents.extend(PyPDFLoader(os.path.join(Config.DOCS_DIR, name)).load())
    return documents


def _split(documents: list) -> list:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=Config.CHUNK_SIZE,
        chunk_overlap=Config.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_documents(documents)


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


def rebuild_vectorstore() -> FAISS:
    """Reconstrói o índice do zero a partir dos documentos atuais."""
    global _vectorstore
    documents = _split(_load_documents())
    if not documents:
        raise ValueError("Nenhum documento encontrado para indexação.")

    logger.info("Indexando %d blocos...", len(documents))
    _vectorstore = FAISS.from_documents(documents, get_embeddings())

    os.makedirs(Config.RAG_DIR, exist_ok=True)
    _vectorstore.save_local(Config.RAG_DIR)
    _save_meta(len(documents))
    logger.info("Índice salvo com %d vetores.", _vectorstore.index.ntotal)
    return _vectorstore


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
        rebuild_vectorstore()
    return _vectorstore


def get_vectorstore():
    """Retorna o índice ou ``None`` se não for possível carregá-lo."""
    try:
        return load_vectorstore()
    except Exception:  # pragma: no cover - depende de arquivos externos
        logger.exception("Falha ao carregar o vectorstore.")
        return None


def retrieve(query: str, vectorstore=None, k: int = None) -> list:
    """Retorna os textos dos ``k`` blocos mais similares à pergunta."""
    if vectorstore is None:
        return []
    k = k or Config.RETRIEVE_K
    return [doc.page_content for doc in vectorstore.similarity_search(query, k=k)]


def stats() -> dict:
    """Resumo da base para a tela de treinamento."""
    total_pdfs = 0
    if os.path.isdir(Config.DOCS_DIR):
        total_pdfs = len(
            [f for f in os.listdir(Config.DOCS_DIR) if f.lower().endswith(".pdf")]
        )
    blocks = _saved_meta().get("blocos", 0)
    vectors = _vectorstore.index.ntotal if _vectorstore is not None else blocks
    return {
        "modelo": Config.EMBED_MODEL,
        "blocos": blocks,
        "vetores": vectors,
        "pdfs": total_pdfs,
    }
