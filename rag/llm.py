"""Integração com as LLMs suportadas.

Cada provedor é registrado em :data:`PROVIDERS` e expõe um gerador de tokens
(streaming). Para adicionar um novo provedor basta escrever a função de
streaming e registrá-la — o resto (UI, validação, roteamento) é automático.
"""
import json
import logging
from typing import Generator, List

import requests
from flask import current_app, has_app_context

from config import Config

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Você é a Assistente Oficial do DOJUFLA,
Centro Acadêmico de Artes Marciais e Ciências do Esporte.

Seu foco principal é esporte em geral, na educação física e com ênfase em artes marciais
como judô, karatê, jiu-jitsu, taekwondo, muay thai, boxe, wrestling,
kung fu, capoeira, aikido e outras modalidades.

Diretrizes:
- Responda com conhecimento técnico quando necessário.
- Explique conceitos de forma clara e didática.
- Se a pergunta for sobre esporte, aprofunde.
- Se for sobre artes marciais, dê prioridade à variedade de modalidades.
- Se a resposta não estiver no contexto, diga:
  "Não encontrei essa informação na base de conhecimento do DOJUFLA."
- Utilize linguagem acadêmica, técnica e institucional.
- Não seja específico com uma única arte marcial, a menos que a pergunta peça isso.

Áreas de domínio:
- Artes marciais
- Treinamento esportivo
- Educação física
- Fisiologia do exercício

HISTÓRICO DA CONVERSA:
{historico}

CONTEXTO:
{contexto}

PERGUNTA:
{pergunta}

RESPOSTA:"""


def _setting(name):
    """Lê um valor da config da app (testes) ou da config global."""
    if has_app_context():
        return current_app.config.get(name, getattr(Config, name))
    return getattr(Config, name)


def montar_prompt(contexto: str, pergunta: str, historico: List[str] = None) -> str:
    """Monta o prompt final enviado à LLM."""
    historico_formatado = "\n".join(historico) if historico else ""
    return _SYSTEM_PROMPT.format(
        historico=historico_formatado,
        contexto=contexto or "(sem contexto)",
        pergunta=pergunta,
    ).strip()


# --------------------------------------------------------------------------- #
# Provedores
# --------------------------------------------------------------------------- #
def _ollama_stream(prompt: str) -> Generator[str, None, None]:
    """Streaming via Ollama (modelo local)."""
    try:
        response = requests.post(
            _setting("OLLAMA_URL"),
            json={
                "model": _setting("OLLAMA_MODEL"),
                "prompt": prompt,
                "stream": True,
                "options": {"temperature": 0.2, "top_p": 0.9, "num_ctx": 4096},
            },
            stream=True,
            timeout=_setting("LLM_TIMEOUT"),
        )
        response.raise_for_status()
        for line in response.iter_lines():
            if line:
                chunk = json.loads(line)
                yield chunk.get("response", "")
    except Exception as exc:  # noqa: BLE001 - devolve a mensagem ao usuário
        logger.exception("Erro no Ollama")
        yield f"\n[ERRO OLLAMA]: {exc}"


def _groq_stream(prompt: str) -> Generator[str, None, None]:
    """Streaming via Groq (API compatível com o formato OpenAI)."""
    api_key = _setting("GROQ_API_KEY")
    if not api_key:
        yield "\n[ERRO GROQ]: variável de ambiente GROQ_API_KEY não configurada."
        return
    try:
        response = requests.post(
            _setting("GROQ_URL"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": _setting("GROQ_MODEL"),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": 2048,
                "stream": True,
            },
            stream=True,
            timeout=_setting("LLM_TIMEOUT"),
        )
        response.raise_for_status()
        yield from _iter_openai_sse(response)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Erro no Groq")
        yield f"\n[ERRO GROQ]: {exc}"


def _gemini_stream(prompt: str) -> Generator[str, None, None]:
    """Streaming via Google Gemini (generateContent com SSE)."""
    api_key = _setting("GEMINI_API_KEY")
    if not api_key:
        yield "\n[ERRO GEMINI]: variável de ambiente GEMINI_API_KEY não configurada."
        return
    try:
        url = f"{_setting('GEMINI_URL')}/models/{_setting('GEMINI_MODEL')}:streamGenerateContent"
        response = requests.post(
            url,
            params={"alt": "sse", "key": api_key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            stream=True,
            timeout=_setting("LLM_TIMEOUT"),
        )
        response.raise_for_status()
        for line in response.iter_lines():
            if not line:
                continue
            decoded = line.decode("utf-8") if isinstance(line, bytes) else line
            if decoded.startswith("data:"):
                decoded = decoded[5:].strip()
            if not decoded or decoded == "[DONE]":
                continue
            try:
                chunk = json.loads(decoded)
            except json.JSONDecodeError:
                continue
            for candidate in chunk.get("candidates", []):
                for part in candidate.get("content", {}).get("parts", []):
                    text = part.get("text")
                    if text:
                        yield text
    except Exception as exc:  # noqa: BLE001
        logger.exception("Erro no Gemini")
        yield f"\n[ERRO GEMINI]: {exc}"


def _iter_openai_sse(response) -> Generator[str, None, None]:
    """Extrai os textos de uma resposta SSE no formato OpenAI (Groq)."""
    for line in response.iter_lines():
        if not line:
            continue
        decoded = line.decode("utf-8") if isinstance(line, bytes) else line
        if decoded.startswith("data:"):
            decoded = decoded[5:].strip()
        if not decoded or decoded == "[DONE]":
            continue
        try:
            chunk = json.loads(decoded)
            text = chunk["choices"][0]["delta"].get("content", "")
            if text:
                yield text
        except (json.JSONDecodeError, KeyError, IndexError):
            continue


# nome -> {label, stream, key_attr}
PROVIDERS = {
    "ollama": {
        "label": "Ollama (Llama 3 · local)",
        "stream": _ollama_stream,
        "key_attr": None,
    },
    "groq": {
        "label": "Groq (Llama 3.3 70B · nuvem)",
        "stream": _groq_stream,
        "key_attr": "GROQ_API_KEY",
    },
    "gemini": {
        "label": "Google Gemini Flash · nuvem",
        "stream": _gemini_stream,
        "key_attr": "GEMINI_API_KEY",
    },
}


def is_configured(name: str) -> bool:
    """True se o provedor existe e está pronto para uso."""
    provider = PROVIDERS.get(name)
    if provider is None:
        return False
    key_attr = provider["key_attr"]
    return bool(_setting(key_attr)) if key_attr else True


def available_providers() -> List[dict]:
    """Provedores configurados, no formato usado pela interface."""
    return [
        {"name": name, "label": provider["label"]}
        for name, provider in PROVIDERS.items()
        if is_configured(name)
    ]


def default_provider() -> str:
    """Provedor padrão, caindo para o primeiro disponível se preciso."""
    if is_configured(_setting("DEFAULT_LLM")):
        return _setting("DEFAULT_LLM")
    available = available_providers()
    return available[0]["name"] if available else "ollama"


def gerar_resposta(
    contexto: str,
    pergunta: str,
    historico: List[str] = None,
    stream: bool = True,
    llm: str = "ollama",
) -> Generator[str, None, None]:
    """Gera a resposta usando o provedor escolhido."""
    provider = PROVIDERS.get(llm)
    if provider is None or not is_configured(llm):
        provider = PROVIDERS[default_provider()]
    prompt = montar_prompt(contexto, pergunta, historico)
    return provider["stream"](prompt)
