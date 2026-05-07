"""
Query the ingested documents: hybrid retrieval (BM25 JSON index + Chroma embeddings),
optional cross-encoder reranking, context packing, prompt templates, then Ollama generation
with optional streaming and response caching.

Usage:
    python -m src.query "what is BM25 indexing?"
    python -m src.query "explain the document processing pipeline" --top-k 8
    python -m src.query "what formats are supported?" --no-llm   # retrieval only (no LLM)
    python -m src.query "..." --model qwen2.5-coder:14b           # override default chat model
    python -m src.query "..." --no-rerank                         # skip cross-encoder rerank
    python -m src.query "..." --stream                            # stream tokens to stdout
"""
from __future__ import annotations

import argparse
import os
import sys
import time

from src.core.bm25_index import BM25Index
from src.core.bm25_search import BM25Search
from src.core.context_optimizer import ContextOptimizer
from src.core.generator import GenerationResult, RAGGenerator
from src.core.hybrid_retriever import HybridRetriever
from src.core.prompt_manager import PromptManager
from src.core.query_processor import QueryProcessor
from src.core.reranker import CrossEncoderReranker, RankedResult
from src.core.response_cache import ResponseCache, cache_key
from src.core.response_processor import ResponseProcessor
from src.core.retrieval_result import RetrievalResult
from src.core.vector_search import VectorSearch
from src.utils.config import Config, load_config
from src.utils.database import VectorDatabase
from src.utils.log import get_logger

logger = get_logger("query")

BM25_INDEX_PATH = "data/embeddings/bm25_index.json"
CHROMA_PATH = "data/embeddings/chroma"
COLLECTION_NAME = "documents"
DEFAULT_LLM_MODEL = os.environ.get("OLLAMA_QUERY_MODEL", "deepseek-r1:8b")


def load_components() -> tuple[BM25Index, VectorDatabase, QueryProcessor]:
    logger.info("Loading BM25 index from %s", BM25_INDEX_PATH)
    index = BM25Index.load(BM25_INDEX_PATH)

    logger.info("Connecting to ChromaDB at %s", CHROMA_PATH)
    db = VectorDatabase(mode="dev", chroma_path=CHROMA_PATH)

    return index, db, QueryProcessor()


def retrieve(
    query_text: str,
    index: BM25Index,
    db: VectorDatabase,
    qp: QueryProcessor,
    top_k: int,
) -> list[RetrievalResult]:
    processed = qp.process_query(query_text)
    bm25_query = " ".join(processed.all_terms)

    hybrid = HybridRetriever(
        BM25Search(index),
        VectorSearch(db, COLLECTION_NAME),
    )
    return hybrid.retrieve(
        bm25_query,
        query_text,
        k=top_k,
        collection_name_for_cache=COLLECTION_NAME,
    )


def run_query(
    query_text: str,
    top_k: int = 5,
    use_llm: bool = True,
    llm_model: str | None = None,
    use_rerank: bool = True,
    stream: bool = False,
    reranker_model: str | None = None,
    config_path: str = "config.yaml",
) -> None:
    try:
        cfg = load_config(config_path)
    except FileNotFoundError:
        cfg = Config()

    model = llm_model or os.environ.get("OLLAMA_QUERY_MODEL") or cfg.generation.model or DEFAULT_LLM_MODEL
    cache = ResponseCache(ttl_seconds=int(cfg.generation.cache_ttl))
    key = cache_key(query_text, model, top_k, response_mode="sync")

    cached = cache.get(key) if use_llm else None
    if cached is not None:
        print(f"\nQuery    : {query_text}")
        print("\n── Cached answer ─────────────────────────────────────────────")
        print(f"(model: {cached.model_name}, latency was {cached.latency_ms:.0f} ms)\n")
        print(cached.response_text)
        print()
        return

    index, db, qp = load_components()

    processed = qp.process_query(query_text)
    print(f"\nQuery    : {query_text}")
    print(f"Intent   : {processed.intent.value}")
    print(f"Tokens   : {processed.tokens}")
    if processed.expanded_terms:
        print(f"Expanded : {processed.expanded_terms}")

    retrieve_k = max(top_k, 20) if use_rerank else top_k
    fused = retrieve(query_text, index, db, qp, top_k=retrieve_k)

    ranked: list[RankedResult] | None = None
    if use_rerank:
        ce_model = reranker_model or cfg.reranker.model
        reranker = CrossEncoderReranker(
            model_name=ce_model,
            batch_size=cfg.reranker.batch_size,
            score_threshold=cfg.reranker.score_threshold,
        )
        ranked = reranker.rerank(query_text, fused, top_k=top_k)
        docs_for_gen: list[RankedResult] | list[RetrievalResult] = ranked
        display_items: list[RetrievalResult] = [r.result for r in ranked]
    else:
        docs_for_gen = fused[:top_k]
        display_items = list(docs_for_gen)

    print(f"\n── Retrieved chunks ({len(display_items)}) ──────────────────────────────")
    if ranked:
        for rr in ranked:
            c = rr.result.to_legacy_dict()
            score_str = f"ce={rr.cross_encoder_score:.4f}"
            print(f"  [{c['source']:6s} {score_str}] {c['id']}")
            print(f"    {c['text'][:120].strip()}...")
    else:
        for r in display_items:
            c = r.to_legacy_dict()
            score_str = f"{c['score']:.4f}" if c.get("score") is not None else "n/a"
            print(f"  [{c['source']:6s} {score_str}] {c['id']}")
            print(f"    {c['text'][:120].strip()}...")

    if use_llm and display_items:
        prompt_manager = PromptManager()
        ctx_opt = ContextOptimizer(
            max_context_tokens=cfg.context.max_tokens,
            tokenizer_name=cfg.context.tokenizer,
        )
        gen = RAGGenerator(
            model_name=model,
            prompt_manager=prompt_manager,
            context_optimizer=ctx_opt,
        )
        query_type = PromptManager.intent_to_query_type(processed.intent)
        rp = ResponseProcessor()

        print("\n── Answer ────────────────────────────────────────────────────")
        print(f"(model: {model})\n")

        if stream:
            t0 = time.perf_counter()
            buf: list[str] = []
            for piece in gen.generate_stream(query_text, docs_for_gen, query_type=query_type):
                print(piece, end="", flush=True)
                buf.append(piece)
            print()
            full = rp.format_response("".join(buf))
            opt = ctx_opt.optimize_context(query_text, docs_for_gen)
            cites = rp.extract_citations(full, opt.documents)
            result = GenerationResult(
                response_text=full,
                citations=cites,
                model_name=model,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                streamed=True,
                optimized_context=opt,
            )
        else:
            result = gen.generate(
                query_text,
                docs_for_gen,
                stream=False,
                query_type=query_type,
            )
            print(result.response_text)

        optimized = result.optimized_context or ctx_opt.optimize_context(
            query_text,
            docs_for_gen,
        )
        val = gen.validate_response(result.response_text, optimized)
        if val.issues:
            logger.info("validation: issues=%s confidence=%.3f", val.issues, val.confidence)

        cache.set(key, result)

    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Query ingested documents")
    parser.add_argument("query", help="Question to ask")
    parser.add_argument("--top-k", type=int, default=5, help="Chunks to retrieve (default: 5)")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM, show retrieved chunks only")
    parser.add_argument(
        "--model",
        default=None,
        help=f"Ollama chat model (default: config.generation.model, {DEFAULT_LLM_MODEL!r}, or OLLAMA_QUERY_MODEL env)",
    )
    parser.add_argument("--no-rerank", action="store_true", help="Skip cross-encoder reranking")
    parser.add_argument("--stream", action="store_true", help="Stream LLM tokens to stdout")
    parser.add_argument(
        "--reranker-model",
        default=None,
        help="Cross-encoder HuggingFace id (default: config.reranker.model)",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to YAML config (default: config.yaml)",
    )
    args = parser.parse_args()

    try:
        run_query(
            args.query,
            top_k=args.top_k,
            use_llm=not args.no_llm,
            llm_model=args.model,
            use_rerank=not args.no_rerank,
            stream=args.stream,
            reranker_model=args.reranker_model,
            config_path=args.config,
        )
    except FileNotFoundError:
        print("Error: BM25 index not found. Run ingestion first:", file=sys.stderr)
        print("  python -m src.ingest --docs data/documents", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
