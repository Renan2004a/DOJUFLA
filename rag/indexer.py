"""Reindexação em segundo plano, com acompanhamento de progresso.

O build completo do índice pode levar minutos (dependendo da base), então ele
roda em uma thread separada. A interface consulta :func:`status` para exibir o
progresso. O índice em memória é trocado apenas ao final, de forma atômica.
"""
import logging
import threading

from rag import vectorstore

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_state = {
    "state": "idle",   # idle | running | done | error
    "stage": "",
    "done": 0,
    "total": 0,
    "message": "",
    "error": None,
}


def _update(**values) -> None:
    with _lock:
        _state.update(values)


def status() -> dict:
    with _lock:
        return dict(_state)


def is_running() -> bool:
    with _lock:
        return _state["state"] == "running"


def start() -> bool:
    """Inicia a reindexação. Retorna False se já houver uma em andamento."""
    with _lock:
        if _state["state"] == "running":
            return False
        _state.update(state="running", stage="Preparando", done=0, total=0,
                      message="", error=None)

    threading.Thread(target=_run, daemon=True).start()
    return True


def _run() -> None:
    try:
        _update(stage="Lendo documentos")
        vectorstore.rebuild_vectorstore(
            progress=lambda done, total: _update(
                stage="Gerando embeddings", done=done, total=total
            )
        )
        info = vectorstore.stats()
        _update(
            state="done",
            stage="Concluído",
            done=info["vetores"],
            total=info["vetores"],
            message=f"Índice reconstruído: {info['vetores']} vetores.",
        )
    except Exception as exc:  # noqa: BLE001 - reportamos o erro na interface
        logger.exception("Falha na reindexação")
        _update(state="error", stage="Erro", message=f"Falha ao reindexar: {exc}",
                error=str(exc))
