# Claude Project Context: Doc-Ingestion

Use this file as the single project-memory attachment for AI chat context. It summarizes what I built, why it matters, how the system works, and which technical decisions define the project.

## Project Summary

Doc-Ingestion is a local-first, citation-aware Retrieval-Augmented Generation (RAG) application that turns private document collections into grounded question-answering experiences. It ingests documents, indexes them for both keyword and semantic retrieval, retrieves relevant evidence, generates answers from that evidence, and returns citations plus quality signals so users can verify where answers came from.

The project is designed as a practical end-to-end AI system, not just a prompt demo. It includes ingestion, document parsing, chunking, embeddings, vector search, BM25 search, hybrid rank fusion, optional reranking, context optimization, multi-provider LLM generation, citation tracking, truthfulness scoring, a FastAPI backend, a Streamlit UI, CLI entry points, Docker deployment support, and offline evaluation tooling.

## Why I Built It

The core problem is that teams often have knowledge scattered across PDFs, Word files, markdown notes, text files, and HTML exports. Traditional keyword search can find matching documents but does not synthesize answers. Generic LLMs can synthesize answers but may hallucinate when they do not know the private document corpus.

Doc-Ingestion solves this gap by grounding each answer in retrieved document chunks. It lets users ask natural-language questions against their own files and inspect the citations and evidence behind the answer.

## Functional Capabilities

- Ingests document collections from local folders or Streamlit uploads.
- Supports multiple document formats: PDF, DOCX, TXT, Markdown, and HTML.
- Splits documents into token-aware chunks suitable for retrieval and prompt construction.
- Builds persistent indexes for both sparse keyword search and dense vector search.
- Lets users ask natural-language questions through Streamlit, FastAPI, or CLI.
- Retrieves relevant evidence using hybrid search rather than a single retrieval method.
- Produces grounded RAG answers with source citations.
- Exposes citation verification and truthfulness-style scoring to help assess answer quality.
- Supports local Ollama models and optional cloud providers: OpenAI, Anthropic, and Gemini.
- Allows provider/model selection per request where credentials are configured.
- Provides Docker Compose support for API, Streamlit, Redis, and Qdrant.
- Includes offline evaluation flows for retrieval and answer quality regression checks.

## User-Facing Surfaces

The same RAG pipeline is available through three interfaces:

- CLI: useful for local testing and scripting document ingestion/query flows.
- FastAPI: production-style API surface with query, streaming query, health, and metrics endpoints.
- Streamlit: demo-friendly UI for asking questions, switching providers/models, uploading files, triggering ingestion, and reviewing answers with citations.

Primary API endpoints:

- `GET /health`
- `GET /metrics`
- `POST /query`
- `POST /query/stream` for server-sent event streaming

## Technical Architecture

The system has two main lifecycle paths: ingestion and query.

Ingestion lifecycle:

1. Files are loaded from `data/documents/` or uploaded through the UI.
2. `DocumentProcessor` parses the source format.
3. Documents are normalized and split into chunks.
4. Chunks are inserted into a BM25 keyword index.
5. Embeddings are generated for chunks.
6. Dense vectors and chunk metadata are persisted in a vector store such as Chroma or Qdrant.

Query lifecycle:

1. User submits a question through CLI, API, or Streamlit.
2. Query is normalized and sent to both BM25 keyword retrieval and vector retrieval.
3. Sparse and dense results are combined with weighted Reciprocal Rank Fusion (RRF).
4. Optional cross-encoder reranking improves final context precision.
5. A context optimizer packs the best chunks into the prompt within a token budget.
6. The provider router sends the prompt to Ollama, OpenAI, Anthropic, or Gemini.
7. The generated answer is post-processed for citations.
8. Citation verification and truthfulness scoring evaluate how well the answer is grounded.
9. Structured response is returned with answer text, citations, source evidence, and quality signals.

## Retrieval Design

Doc-Ingestion uses hybrid retrieval because private document search often needs both exact matching and semantic matching.

- BM25 handles exact terms, identifiers, names, acronyms, and rare keywords.
- Vector search handles semantic similarity when the user's wording differs from the documents.
- Weighted Reciprocal Rank Fusion combines both result sets into one ranked list.
- Cross-encoder reranking can rescore query-document pairs to improve the final top-k context.

This design is more robust than pure vector search because it preserves lexical precision while still benefiting from semantic retrieval.

## Generation And Grounding Design

The project uses a grounding contract:

1. Retrieve evidence first.
2. Generate answers only from retrieved context.
3. Attach citations to source chunks.
4. Verify citations and score answer support.

The prompt instructs the model to answer from context and cite sources. The citation system maps generated citation markers back to retrieved chunks, verifies support, and exposes confidence or truthfulness-style signals.

Truthfulness-related response fields can include:

- `nli_faithfulness`: estimated fraction of answer sentences supported by retrieved chunks.
- `citation_groundedness`: average citation verification score.
- `uncited_claims`: count of answer sentences without citation markers.
- `score`: weighted aggregate of grounding and faithfulness signals.

## LLM Provider Strategy

The app is local-first but not local-only.

- Ollama is the default local provider for private/offline workflows.
- OpenAI, Anthropic, and Gemini are supported as optional cloud providers.
- API keys are environment-driven or session-scoped through Streamlit.
- Provider/model routing is configurable and can be selected per request.
- Cloud providers remain optional so the project can run locally without hard dependency on hosted LLM APIs.

## Tech Stack

- Language: Python
- UI: Streamlit
- API: FastAPI, Pydantic, Uvicorn
- Document processing: PyPDF2, python-docx, BeautifulSoup, Markdown/text parsing
- Sparse retrieval: BM25
- Dense retrieval: sentence-transformers/Ollama embeddings with Chroma or Qdrant
- Ranking: weighted RRF and `cross-encoder/ms-marco-MiniLM-L-6-v2`
- Generation providers: Ollama, OpenAI, Anthropic, Gemini
- Evaluation: NLI faithfulness, citation groundedness, retrieval/generation metrics, golden datasets
- Operations: Docker Compose, Redis-backed rate limiting with in-memory fallback, Hugging Face Spaces deployment

## Important Code Areas

- `src/ingest.py`: CLI document ingestion entry point.
- `src/query.py`: CLI query entry point.
- `src/core/`: retrieval, reranking, orchestration, generation, context optimization, citation logic, provider routing.
- `src/api/`: FastAPI app, routes, models, authentication, rate limiting, streaming behavior.
- `src/web/`: Streamlit app and ingestion/query UI behavior.
- `src/utils/`: configuration, logging, and vector database integration.
- `src/evaluation/`: truthfulness scoring and retrieval/generation quality metrics.
- `evals/`: offline evaluation harness, smoke/golden datasets, report generation.
- `docker/`: Docker Compose stack for API, Streamlit, Redis, and Qdrant.
- `spaces/`: Hugging Face Spaces deployment files.
- `config.yaml`: central configuration for providers, retrieval, generation, API auth, rate limits, and evaluation.

## Deployment And Runtime Modes

Local source mode:

- Create a Python virtual environment.
- Install requirements.
- Run ingestion against `data/documents/`.
- Start FastAPI on port `8000`.
- Start Streamlit on port `8501`.

Docker mode:

- Uses `docker/docker-compose.yml`.
- Starts API, Streamlit, Redis, and Qdrant.
- Redis supports distributed rate limiting.
- If Redis is unavailable, the API falls back to an in-memory limiter.
- Hugging Face model caches can be persisted to avoid repeated reranker downloads.

Hosted demo mode:

- The project includes a Hugging Face Spaces demo.
- In demo profile mode, Streamlit can execute queries in-process through the shared orchestrator to avoid localhost API startup issues in hosted environments.
- Local non-demo mode uses the split architecture where Streamlit calls FastAPI over HTTP.

## Security And Operational Notes

- API auth uses configured API keys or `DOC_API_KEYS`.
- Streamlit can pass provider keys session-only without writing them to disk.
- Cloud provider requests require appropriate API keys.
- Rate limiting can use Redis with fallback to in-memory limiting.
- API emits structured audit-style events such as auth success/failure and query success/failure.
- Secrets should remain environment-driven and should not be hardcoded.

## Evaluation And Quality Approach

The project includes quality checks at several layers:

- Retrieval quality through precision/recall-style metrics, MRR, NDCG, MAP, and hit rate concepts.
- Generation quality through faithfulness, relevance, citation coverage, and groundedness.
- Inline response scoring through the `truthfulness` block.
- Offline evaluation using golden and smoke datasets.
- Unit and integration tests for behavior validation.

Typical validation commands:

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/unit -q
PYTHONPATH=. .venv/bin/python -m pytest tests/integration -q
```

Typical eval command:

```bash
PYTHONPATH=. python -m evals.run_evals --dataset evals/datasets/smoke.jsonl --mock --no-nli --output evals/reports/
```

## Project Status

Completed phases:

- Phase 1: multi-format ingestion, BM25 indexing, Chroma vector storage.
- Phase 2: hybrid retrieval, query processing, weighted RRF fusion.
- Phase 3: cross-encoder reranking, context optimization, RAG generation.
- Phase 4: citation tracking/verification, FastAPI endpoints, Streamlit query and ingest UI, multi-provider model routing, streaming query support, API auth/rate limiting.

Planned or next improvements:

- Production deployment hardening.
- Observability dashboards and richer operational metrics.
- Managed auth and tenant/session isolation.
- Expanded evaluation harness for provider comparison and regression tracking.
- Continued refinement of Streamlit-to-React/container cutover planning if the UI evolves.

## Portfolio Framing

This project demonstrates that I built a complete RAG product and reference architecture, including:

- End-to-end document ingestion and retrieval infrastructure.
- Practical hybrid search design using sparse and dense methods.
- Ranking and context optimization before generation.
- Citation-aware answer generation with source verification.
- Multi-provider LLM abstraction rather than a single hardcoded model.
- API, UI, CLI, Docker, and hosted demo deployment surfaces.
- Quality evaluation and operational considerations beyond the happy path.

The strongest technical point is that the app treats RAG as a system with retrieval quality, ranking quality, context control, generation behavior, citations, evaluation, and operations, rather than as a simple "send documents to an LLM" workflow.

## How Future AI Assistants Should Use This Context

When helping with this project, assume the intended architecture is:

- local-first
- retrieval-grounded
- citation-aware
- provider-configurable
- testable through API, UI, CLI, and eval harnesses

Prefer extending existing modules instead of creating parallel abstractions. Preserve the hybrid retrieval path of BM25 plus vector search, weighted RRF, optional reranking, citation verification, and structured query responses unless explicitly asked to redesign the system.
