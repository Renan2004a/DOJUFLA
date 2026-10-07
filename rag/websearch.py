"""Busca na web (DuckDuckGo) para complementar a base interna do RAG.

Não exige chave de API. Se quiser trocar por um provedor pago (ex.: Tavily),
basta reimplementar :func:`search` mantendo o mesmo formato de retorno.
"""
import logging

from config import Config

logger = logging.getLogger(__name__)


def is_available() -> bool:
    try:
        import ddgs  # noqa: F401
        return True
    except Exception:  # pragma: no cover - dependência opcional
        return False


def search(query: str, k: int = None) -> list:
    """Retorna até ``k`` resultados da web: ``{titulo, url, trecho}``."""
    if not query.strip():
        return []
    k = k or Config.WEB_SEARCH_K
    try:
        from ddgs import DDGS

        resultados = DDGS().text(query, max_results=k)
    except Exception:  # noqa: BLE001 - web é opcional; nunca deve quebrar o chat
        logger.exception("Falha na busca web")
        return []

    itens = []
    for r in resultados or []:
        url = r.get("href") or r.get("url")
        if not url:
            continue
        itens.append({
            "titulo": r.get("title") or url,
            "url": url,
            "trecho": r.get("body") or r.get("snippet") or "",
        })
    return itens
