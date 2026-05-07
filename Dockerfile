# Single-process image: FastAPI serves the React SPA from /app/static and API routes under the same port.
# Hugging Face Docker Spaces expects a Dockerfile at the repository root; local builds use the same file:
#   docker build -t doc-ingest .
# Compose: docker/docker-compose.yml (build context is repo root).

FROM node:20-bookworm-slim AS frontend-builder
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim

WORKDIR /app

# Install system deps needed by python-magic and runtime health checks.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/base.txt requirements/base.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements/base.txt

COPY --from=frontend-builder /frontend/dist /app/static

COPY src/ src/
COPY scripts/ scripts/
COPY tests/ tests/
COPY config.yaml config.yaml
COPY README.md README.md
COPY Docs/ Docs/

ENV ENV=prod
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV PORT=8000
ENV OLLAMA_BASE_URL=http://host.docker.internal:11434
ENV HF_HOME=/app/.cache/huggingface
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface/transformers
ENV SENTENCE_TRANSFORMERS_HOME=/app/.cache/huggingface/sentence_transformers

# Preload reranker model at build time to avoid runtime downloads.
RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

EXPOSE 8000

# HF Spaces runs the container as UID 1000; match that to avoid permission issues.
RUN useradd -m -u 1000 appuser && mkdir -p /app/.cache/huggingface && chown -R appuser:appuser /app
USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD sh -c 'curl -fsS "http://127.0.0.1:${PORT:-8000}/health" || exit 1'

# PORT is honored for Hugging Face (app_port / runtime) and other platforms.
CMD ["sh", "-c", "exec uvicorn src.api.main:app --host 0.0.0.0 --port \"${PORT:-8000}\" --workers 1"]
