"""Integração com as LLMs suportadas (Ollama local e Groq na nuvem).

Expõe uma única função, :func:`gerar_resposta`, que devolve um gerador de
tokens (streaming), independentemente do provedor escolhido.
"""
import json
import logging
from typing import Generator, List, Union

import requests

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


def montar_prompt(contexto: str, pergunta: str, historico: List[str] = None) -> str:
    """Monta o prompt final enviado à LLM."""
    historico_formatado = "\n".join(historico) if historico else ""
    return _SYSTEM_PROMPT.format(
        historico=historico_formatado,
        contexto=contexto or "(sem contexto)",
        pergunta=pergunta,
    ).strip()


def _ollama_stream(prompt: str) -> Generator[str, None, None]:
    """Streaming via Ollama (modelo local)."""
    try:
        response = requests.post(
            Config.OLLAMA_URL,
            json={
                "model": Config.OLLAMA_MODEL,
                "prompt": prompt,
                "stream": True,
                "options": {"temperature": 0.2, "top_p": 0.9, "num_ctx": 4096},
            },
            stream=True,
            timeout=Config.OLLAMA_TIMEOUT,
        )
        response.raise_for_status()
        for line in response.iter_lines():
            if line:
                chunk = json.loads(line)
                yield chunk.get("response", "")
    except Exception as exc:  # noqa: BLE001 - queremos devolver a mensagem ao usuário
        logger.exception("Erro no Ollama")
        yield f"\n[ERRO OLLAMA]: {exc}"


def _groq_stream(prompt: str) -> Generator[str, None, None]:
    """Streaming via Groq (API na nuvem)."""
    if not Config.GROQ_API_KEY:
        yield "\n[ERRO GROQ]: variável de ambiente GROQ_API_KEY não configurada."
        return
    try:
        response = requests.post(
            Config.GROQ_URL,
            headers={
                "Authorization": f"Bearer {Config.GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": Config.GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": 2048,
                "stream": True,
            },
            stream=True,
            timeout=Config.OLLAMA_TIMEOUT,
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
                text = chunk["choices"][0]["delta"].get("content", "")
                if text:
                    yield text
            except (json.JSONDecodeError, KeyError, IndexError):
                continue
    except Exception as exc:  # noqa: BLE001
        logger.exception("Erro no Groq")
        yield f"\n[ERRO GROQ]: {exc}"


_ENGINES = {
    "ollama": _ollama_stream,
    "groq": _groq_stream,
}


def gerar_resposta(
    contexto: str,
    pergunta: str,
    historico: List[str] = None,
    stream: bool = True,
    llm: str = "ollama",
) -> Union[str, Generator[str, None, None]]:
    """Gera a resposta usando o provedor escolhido (padrão: Ollama)."""
    prompt = montar_prompt(contexto, pergunta, historico)
    engine = _ENGINES.get(llm, _ollama_stream)
    return engine(prompt)
