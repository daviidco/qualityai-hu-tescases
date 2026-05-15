FROM python:3.11-slim

# Herramientas de compilación para ChromaDB, sentence-transformers y C-extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ curl fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Dependencias (capa cacheada) ──────────────────────────────────────────────
COPY be-chatbot-ai/requirements.txt ./be-chatbot-ai/requirements.txt
RUN pip install --no-cache-dir -r ./be-chatbot-ai/requirements.txt

# ── Pre-descargar modelos locales para arranque sin internet ──────────────────
# Cross-encoder reranker (~85 MB)
RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

# ── Código fuente ─────────────────────────────────────────────────────────────
COPY modulo3_quality_pipeline/ ./modulo3_quality_pipeline/
COPY be-chatbot-ai/             ./be-chatbot-ai/

WORKDIR /app/be-chatbot-ai

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
