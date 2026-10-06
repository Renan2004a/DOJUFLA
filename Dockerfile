# Dockerfile para Hugging Face Spaces (SDK: docker)
FROM python:3.12-slim

# Bibliotecas de sistema exigidas pelo FAISS (OpenMP)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface

COPY requirements.txt .

# Instala o torch na versão CPU (a padrão do PyPI é CUDA e fica gigante),
# depois as demais dependências + gunicorn.
RUN pip install --no-cache-dir torch==2.4.1 --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt gunicorn==22.0.0

# Pré-baixa o modelo de embeddings para o start ser mais rápido
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY . .

EXPOSE 7860
CMD ["gunicorn", "app:app", "--workers", "1", "--bind", "0.0.0.0:7860", "--timeout", "180"]
