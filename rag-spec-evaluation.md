# RAG Spec Evaluation Report

## Context

This is a gap analysis of the Doc-Ingestion app against a production-grade RAG spec across three phases. The goal is to identify what is built, what partially meets the spec, and what is missing or misaligned.

---

## Spec vs. Implementation: Detailed Evaluation

### Phase 1 — Fundamentals

| Requirement | Status | Detail |
|---|---|---|
| Ingest documents | ✅ Built | PDF, DOCX, TXT, MD, HTML via `src/core/document_processor.py` |
| 500–800 **token** chunks | ⚠️ Partial / Misaligned | Chunking uses **characters** (default: 1000 chars, 200 overlap), not tokens. Spec requires token-based chunking (500–800 tokens). No tokenizer is applied during chunking. |
| 100-token overlap | ⚠️ Partial / Misaligned | Overlap is 200 characters, not 100 tokens. Same root issue: characters vs. tokens. |
| Vector store (Chroma or Qdrant) | ✅ Built | ChromaDB for dev (`data/embeddings/chroma`), Qdrant optional for prod. Both present in `src/utils/database.py`. |

**Gap to fix:**
- `src/core/document_processor.py` `chunk_text()` method uses character sliding window. Needs to be replaced with a tokenizer-aware splitter (e.g., `tiktoken` or `transformers` tokenizer) targeting 500–800 tokens with 100-token overlap.
- `config.yaml` `chunk_size: 1000` and `overlap: 200` need to change to token units.

---

### Phase 2 — Hybrid Retrieval + Re-ranking

| Requirement | Status | Detail |
|---|---|---|
| BM25 keyword search | ✅ Built | `src/core/bm25_search.py`, `BM25Search` using `rank-bm25` |
| Vector semantic search | ✅ Built | `src/core/vector_search.py`, `VectorSearch` with ChromaDB |
| Hybrid retrieval combining both | ✅ Built | `src/core/hybrid_retriever.py`, `HybridRetriever` with Reciprocal Rank Fusion (RRF), parallel execution |
| Cross-encoder re-ranker | ✅ Built | `src/core/reranker.py`, `CrossEncoderReranker` using `cross-encoder/ms-marco-MiniLM-L-6-v2` |

**Phase 2 is fully built and exceeds the spec** (adds RRF fusion, LRU caching, confidence scoring, configurable weights).

---

### Phase 3 — Evaluation Dataset + CI/CD

| Requirement | Status | Detail |
|---|---|---|
| Golden dataset of 50–200 Q&A pairs | ⚠️ Missing | Only `evals/datasets/smoke.jsonl` (~few entries, 1 KB) and `evals/datasets/sample.jsonl` (~6 KB, estimated ~10–15 pairs). Neither meets the 50–200 pair threshold. |
| Offline evaluation script | ✅ Built | `evals/run_evals.py` (504 lines) with 8+ metrics: answer_relevancy, context_precision, context_recall, ROUGE-L, citation_rate, faithfulness |
| CI/CD pipeline integration | ⚠️ Partial | `.github/workflows/ci.yml` has `evals-smoke` job, but it runs with `--mock` flag (MockPipeline). It does **not** measure real faithfulness — it tests the eval harness, not the RAG pipeline. |
| Measure faithfulness | ⚠️ Partial | NLI faithfulness via `src/evaluation/truthfulness.py` exists. RAGAS integration exists in `evals/adapters/ragas_llm_adapter.py` but is optional (requires `ragas>=0.2`, `langchain-core` extra deps) and not wired into CI. |

---

### Recommended Tech Stack Alignment

| Recommendation | Status | Detail |
|---|---|---|
| LangChain or LangGraph | ❌ Not used | Core pipeline uses direct HTTP API calls (`src/core/llm_provider.py`). LangChain only appears as a thin adapter in `evals/adapters/ragas_llm_adapter.py` to satisfy RAGAS interface — it is not the orchestration framework. |
| ChromaDB or Qdrant | ✅ Built | Both present |
| Ragas for evaluation | ⚠️ Optional / Incomplete | Present as optional adapter, not enforced. CI runs MockPipeline without RAGAS. |

---

## Summary: What Is Missing

### Must-Fix (spec violations)

1. **Token-based chunking** — `src/core/document_processor.py:chunk_text()` uses character counts, not tokens. Replace with tokenizer-aware chunking (e.g., `tiktoken`) targeting 500–800 tokens, 100-token overlap. Update `config.yaml` units accordingly.

2. **Golden evaluation dataset (50–200 pairs)** — `evals/datasets/` only has smoke (~few entries) and sample (~10–15 pairs). Need to create a curated dataset of at least 50 ground-truth Q&A pairs with reference contexts, authored against real ingested documents.

3. **CI/CD runs real faithfulness evaluation** — The `evals-smoke` GitHub Actions job uses `--mock`. A CI job that runs `LivePipeline` against the golden dataset (or a representative subset) and gates on a faithfulness threshold is required by the spec.

### Should-Fix (partial alignment)

4. **RAGAS made non-optional** — RAGAS faithfulness should be a hard dependency in `evals/`, not a conditional import behind `try/except`. The eval report should always include RAGAS faithfulness score.

5. **LangChain / LangGraph adoption** — The spec recommends LangChain/LangGraph as the orchestration layer. Currently the pipeline is custom HTTP. This is a tech stack deviation, not a functional gap — worth noting but lower priority than items 1–3.

---

## What Is Already Production-Grade (exceeds spec)

- Full hybrid retrieval with RRF fusion, parallel execution, and LRU caching
- Cross-encoder reranking with batch scoring and threshold filtering
- Multi-provider LLM routing (Ollama, OpenAI, Anthropic, Gemini) with streaming
- NLI-based inline truthfulness scoring in the serving path
- Citation tracking and verification
- Response caching (Redis + in-memory fallback)
- Rate limiting, API key auth, audit logging
- Comprehensive IR metrics module (P@K, R@K, MRR, MAP, NDCG)
- Unit + integration test coverage with CI

---

## Verification Steps (after fixes)

1. After token-based chunking: ingest a known document, query it, verify chunk boundaries fall within 500–800 token range using `tiktoken` inspection script.
2. After golden dataset: run `python -m evals.run_evals --dataset evals/datasets/golden.jsonl --live` and confirm dataset size ≥ 50.
3. After CI wiring: confirm GitHub Actions `evals-golden` job fails when faithfulness drops below threshold (e.g., `nli_faithfulness < 0.7`).