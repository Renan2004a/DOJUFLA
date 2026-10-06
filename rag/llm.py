import os
import requests
from typing import List, Generator, Union
import json

# ===================== CONFIG (variáveis de ambiente) =====================
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_URL = os.environ.get("GROQ_URL", "https://api.groq.com/openai/v1/chat/completions")


def montar_prompt(contexto: str, pergunta: str, historico: List[str] = None) -> str:
    historico_formatado = ""

    if historico:
        historico_formatado = "\n".join(historico)

    prompt = f"""
Você é a Assistente Oficial do DOJUFLA,
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
{historico_formatado}

CONTEXTO:
{contexto}

PERGUNTA:
{pergunta}

RESPOSTA:
"""
    return prompt.strip()


# ===================== OLLAMA =====================
def _ollama_stream(prompt: str) -> Generator[str, None, None]:
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": True,
                "options": {"temperature": 0.2, "top_p": 0.9, "num_ctx": 4096}
            },
            stream=True,
            timeout=60
        )
        for line in response.iter_lines():
            if line:
                chunk = json.loads(line)
                yield chunk.get("response", "")
    except Exception as e:
        yield f"\n[ERRO OLLAMA]: {str(e)}"


# ===================== GROQ =====================
def _groq_stream(prompt: str) -> Generator[str, None, None]:
    if not GROQ_API_KEY:
        yield "\n[ERRO GROQ]: variável de ambiente GROQ_API_KEY não configurada."
        return
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        body = {
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 2048,
            "stream": True
        }
        response = requests.post(GROQ_URL, headers=headers, json=body, stream=True, timeout=60)

        for line in response.iter_lines():
            if line:
                decoded = line.decode("utf-8") if isinstance(line, bytes) else line
                if decoded.startswith("data:"):
                    decoded = decoded[5:].strip()
                if decoded and decoded != "[DONE]":
                    try:
                        chunk = json.loads(decoded)
                        text = chunk["choices"][0]["delta"].get("content", "")
                        if text:
                            yield text
                    except:
                        pass
    except Exception as e:
        yield f"\n[ERRO GROQ]: {str(e)}"


# ===================== INTERFACE PRINCIPAL =====================
def gerar_resposta(
    contexto: str,
    pergunta: str,
    historico: List[str] = None,
    stream: bool = False,
    llm: str = "ollama"
) -> Union[str, Generator[str, None, None]]:

    prompt = montar_prompt(contexto, pergunta, historico)

    roteador = {
        "ollama": _ollama_stream,
        "groq":   _groq_stream,
    }

    gerador = roteador.get(llm, _ollama_stream)
    return gerador(prompt)