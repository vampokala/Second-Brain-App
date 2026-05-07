"""Offline RAG evaluation harness.

Runs a golden dataset through the live RAG pipeline and computes:
  - faithfulness (NLI-based, via TruthfulnessScorer)
  - answer_relevancy (cosine similarity between question and answer)
  - context_precision (retrieved chunk P@K vs ground-truth contexts)
  - context_recall (retrieved chunk R@K vs ground-truth contexts)
  - answer_correctness (ROUGE-L against ground-truth reference)
  - citation_rate (fraction of answers with at least one supported citation)
  - citation_resolution_rate (fraction of answers with at least one resolved citation marker)
  - mean_citation_groundedness (average citation verification score)

When ragas>=0.2 and langchain-core are installed (requirements/eval.txt),
the harness also computes RAGAS faithfulness and answer relevancy using an
LLM judge routed through LLMProviderRouter.

Usage:
    python -m evals.run_evals \\
        --dataset evals/datasets/sample.jsonl \\
        --judge-provider ollama \\
        --judge-model qwen2.5:7b \\
        --output evals/reports/

    # Smoke test (no real LLM required with --mock)
    python -m evals.run_evals \\
        --dataset evals/datasets/smoke.jsonl \\
        --mock \\
        --output evals/reports/
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("evals")


# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------

def load_dataset(path: str) -> List[Dict[str, Any]]:
    samples = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    if not samples:
        raise ValueError(f"Dataset {path} is empty")
    return samples


# ---------------------------------------------------------------------------
# Mock pipeline (for CI / offline testing)
# ---------------------------------------------------------------------------

class MockPipeline:
    """Returns deterministic answers based on question keywords."""

    def run(self, question: str) -> Dict[str, Any]:
        answer_map = {
            "rag": "RAG stands for Retrieval-Augmented Generation. It enhances LLM responses by retrieving relevant documents before generation.",
            "bm25": "BM25 is a ranking function for information retrieval that scores document relevance using term frequency and document length normalization.",
            "vector": "A vector database stores and indexes high-dimensional vector embeddings for fast similarity search.",
        }
        q = question.lower()
        answer = "This is a sample answer for testing purposes."
        for kw, ans in answer_map.items():
            if kw in q:
                answer = ans
                break
        return {
            "answer": answer,
            "retrieved": [{"id": "mock-chunk-1", "text": f"Context for: {question[:40]}"}],
            "citations": [{"chunk_id": "mock-chunk-1", "resolved": True, "verification_score": 0.75, "verification": "supported"}],
        }


# ---------------------------------------------------------------------------
# Live pipeline wrapper
# ---------------------------------------------------------------------------

class LivePipeline:
    def __init__(self, provider: str, model: Optional[str]) -> None:
        from src.core.rag_orchestrator import QueryRequest, RAGOrchestrator
        from src.utils.config import load_config

        cfg = load_config("config.yaml")
        self._orchestrator = RAGOrchestrator(cfg)
        self._provider = provider
        self._model = model

    def run(self, question: str) -> Dict[str, Any]:
        from src.core.rag_orchestrator import QueryRequest

        req = QueryRequest(
            query_text=question,
            provider=self._provider,
            model=self._model,
            include_citations=True,
            use_rerank=True,
        )
        result = self._orchestrator.run(req)
        return {
            "answer": result.answer,
            "retrieved": [r.to_legacy_dict() for r in result.retrieved],
            "citations": result.citations,
        }


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def _cosine_sim(a: List[float], b: List[float]) -> float:
    import math

    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


_embed_model: Any = None


def _hash_embedding(text: str, dim: int = 384) -> List[float]:
    """Deterministic bag-of-features vector (no network). Used when MiniLM cannot load."""
    import hashlib
    import math
    import re

    vec = [0.0] * dim
    text_lower = text.lower().strip()
    if not text_lower:
        return vec
    for w in re.findall(r"[a-z0-9]+", text_lower):
        h = int(hashlib.md5(w.encode(), usedforsecurity=False).hexdigest()[:8], 16)
        vec[h % dim] += 1.0
    if len(text_lower) >= 3:
        for i in range(len(text_lower) - 2):
            tri = text_lower[i : i + 3]
            h = int(hashlib.md5(tri.encode(), usedforsecurity=False).hexdigest()[:8], 16)
            vec[h % dim] += 0.35
    mag = math.sqrt(sum(x * x for x in vec))
    if mag == 0:
        return vec
    return [x / mag for x in vec]


def _embed(texts: List[str]) -> List[List[float]]:
    global _embed_model
    if _embed_model == "hash":
        return [_hash_embedding(t) for t in texts]
    if _embed_model is not None:
        vecs = _embed_model.encode(texts, show_progress_bar=False)
        return [v.tolist() for v in vecs]
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]

        _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
        vecs = _embed_model.encode(texts, show_progress_bar=False)
        return [v.tolist() for v in vecs]
    except Exception:
        logger.warning(
            "sentence-transformers unavailable or model download failed; "
            "using deterministic hash embeddings for answer_relevancy."
        )
        _embed_model = "hash"
        return [_hash_embedding(t) for t in texts]


def answer_relevancy(question: str, answer: str) -> float:
    if not question.strip() or not answer.strip():
        return 0.0
    vecs = _embed([ question, answer])
    return _cosine_sim(vecs[0], vecs[1])


def context_precision_at_k(
    retrieved_texts: List[str],
    reference_contexts: List[str],
    k: int = 5,
) -> float:
    if not retrieved_texts or not reference_contexts:
        return 0.0
    top = retrieved_texts[:k]
    if not top:
        return 0.0
    # A retrieved chunk is relevant if it has >30% token overlap with any reference context.
    def _tokens(t: str) -> set:
        import re
        return {w for w in re.findall(r"[a-z0-9]+", t.lower()) if len(w) > 2}

    ref_tokens = [_tokens(c) for c in reference_contexts]
    hits = 0
    for chunk in top:
        chunk_toks = _tokens(chunk)
        if not chunk_toks:
            continue
        if any(len(chunk_toks & rt) / max(len(chunk_toks), 1) >= 0.3 for rt in ref_tokens):
            hits += 1
    return hits / len(top)


def context_recall(
    retrieved_texts: List[str],
    reference_contexts: List[str],
    k: int = 5,
) -> float:
    if not reference_contexts:
        return 1.0
    if not retrieved_texts:
        return 0.0

    import re

    def _tokens(t: str) -> set:
        return {w for w in re.findall(r"[a-z0-9]+", t.lower()) if len(w) > 2}

    top_tokens = [_tokens(c) for c in retrieved_texts[:k]]
    covered = 0
    for ref in reference_contexts:
        ref_toks = _tokens(ref)
        if not ref_toks:
            covered += 1
            continue
        if any(len(ref_toks & ct) / max(len(ref_toks), 1) >= 0.3 for ct in top_tokens):
            covered += 1
    return covered / len(reference_contexts)


def answer_correctness_rouge(answer: str, reference: str) -> float:
    try:
        from rouge_score import rouge_scorer  # type: ignore[import-untyped]

        scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
        s = scorer.score(reference, answer)
        return float(s["rougeL"].fmeasure)
    except ImportError:
        return 0.0


def citation_rate(citations: List[Dict[str, Any]]) -> float:
    supported = [c for c in citations if str(c.get("verification", "")).lower() == "supported"]
    return 1.0 if supported else 0.0


def citation_resolution_rate(citations: List[Dict[str, Any]]) -> float:
    resolved = [c for c in citations if c.get("resolved")]
    return 1.0 if resolved else 0.0


def mean_citation_groundedness(citations: List[Dict[str, Any]]) -> float:
    if not citations:
        return 0.0
    scores = [float(c.get("verification_score", 0.0)) for c in citations]
    return sum(scores) / len(scores)


# ---------------------------------------------------------------------------
# Optional RAGAS integration
# ---------------------------------------------------------------------------

def _try_ragas_faithfulness(
    answer: str,
    retrieved_texts: List[str],
    question: str,
    ragas_llm: Any,
) -> Optional[float]:
    """Run RAGAS Faithfulness metric; returns None if ragas is unavailable."""
    try:
        from ragas import EvaluationDataset  # type: ignore[import-untyped]
        from ragas import evaluate
        from ragas.dataset_schema import SingleTurnSample  # type: ignore[import-untyped]
        from ragas.metrics import Faithfulness  # type: ignore[import-untyped]

        sample = SingleTurnSample(
            user_input=question,
            response=answer,
            retrieved_contexts=retrieved_texts,
        )
        ds = EvaluationDataset(samples=[sample])
        result = evaluate(dataset=ds, metrics=[Faithfulness()], llm=ragas_llm)
        row = result.to_pandas()
        return float(row["faithfulness"].iloc[0])
    except Exception as exc:
        logger.debug("RAGAS faithfulness skipped: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Main evaluation loop
# ---------------------------------------------------------------------------

def _retrieved_dicts_to_nli_sources(
    question: str,
    retrieved_chunks: List[Dict[str, Any]],
    *,
    max_context_tokens: int,
    tokenizer_name: str,
) -> tuple[List[str], str]:
    """Match inline `/query` truthfulness: NLI over context-optimizer output, not raw top-k chunks."""
    if not retrieved_chunks:
        return [], "empty"
    try:
        from src.core.context_optimizer import ContextOptimizer
        from src.core.retrieval_result import RetrievalResult
    except ImportError as exc:
        logger.warning("Context optimizer import failed; using raw retrieved chunks for NLI: %s", exc)
        return [str(r.get("text", r.get("preview", ""))) for r in retrieved_chunks], "raw_fallback_import_error"

    wrapped = [
        RetrievalResult(
            id=str(r.get("id", "")),
            text=str(r.get("text", r.get("preview", ""))),
            metadata=dict(r.get("metadata") or {}),
            fusion_score=float(r.get("score") or 0.0),
        )
        for r in retrieved_chunks
    ]
    opt = ContextOptimizer(
        max_context_tokens=max_context_tokens,
        tokenizer_name=tokenizer_name,
    ).optimize_context(question, wrapped)
    optimized = [str(d.get("text", "")) for d in opt.documents if d.get("text")]
    if not optimized:
        logger.warning("Context optimizer produced empty docs; using raw retrieved chunks for NLI")
        return [str(r.get("text", r.get("preview", ""))) for r in retrieved_chunks], "raw_fallback_empty_optimized"
    return optimized, "optimized"


def evaluate_dataset(
    samples: List[Dict[str, Any]],
    pipeline: Any,
    ragas_llm: Any = None,
    faithfulness_scorer: Any = None,
) -> List[Dict[str, Any]]:
    results = []
    for i, sample in enumerate(samples, 1):
        question = sample["user_input"]
        reference = sample.get("reference", "")
        reference_contexts = sample.get("reference_contexts", [])

        logger.info("[%d/%d] %s", i, len(samples), question[:60])
        t0 = time.perf_counter()

        try:
            out = pipeline.run(question)
        except Exception as exc:
            logger.warning("Pipeline error for sample %d: %s", i, exc)
            out = {"answer": "", "retrieved": [], "citations": []}

        answer = out.get("answer", "")
        retrieved_chunks = out.get("retrieved", [])
        citations = out.get("citations", [])
        retrieved_texts = [
            str(r.get("text", r.get("preview", ""))) for r in retrieved_chunks
        ]

        nli_source_texts = retrieved_texts
        if faithfulness_scorer is not None and retrieved_chunks:
            try:
                from src.utils.config import load_config

                _cfg = load_config("config.yaml")
                nli_source_texts, nli_source_mode = _retrieved_dicts_to_nli_sources(
                    question,
                    retrieved_chunks,
                    max_context_tokens=_cfg.context.max_tokens,
                    tokenizer_name=_cfg.context.tokenizer,
                )
            except Exception as exc:
                logger.warning("NLI source parity fallback to raw chunks: %s", exc)
                nli_source_texts = retrieved_texts
                nli_source_mode = "raw_fallback_exception"
        else:
            nli_source_mode = "raw_default"

        # Core metrics
        row: Dict[str, Any] = {
            "question": question,
            "answer": answer[:300],
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
            "answer_relevancy": round(answer_relevancy(question, answer), 3),
            "context_precision": round(context_precision_at_k(retrieved_texts, reference_contexts), 3),
            "context_recall": round(context_recall(retrieved_texts, reference_contexts), 3),
            "answer_correctness_rouge": round(answer_correctness_rouge(answer, reference), 3),
            "citation_rate": citation_rate(citations),
            "citation_resolution_rate": citation_resolution_rate(citations),
            "mean_citation_groundedness": round(mean_citation_groundedness(citations), 3),
        }
        row["nli_source_mode"] = nli_source_mode

        # Inline faithfulness (NLI-based)
        if faithfulness_scorer is not None and answer.strip():
            try:
                t_result = faithfulness_scorer.score(answer, nli_source_texts, citations)
                row["nli_faithfulness"] = t_result.nli_faithfulness
                row["truthfulness_score"] = t_result.score
                row["score"] = t_result.score
                row["citation_groundedness"] = t_result.citation_groundedness
                row["uncited_claims"] = t_result.uncited_claims
            except Exception as exc:
                logger.debug("NLI faithfulness error: %s", exc)

        # RAGAS faithfulness (LLM-based, optional)
        if ragas_llm is not None and answer.strip():
            ragas_f = _try_ragas_faithfulness(answer, retrieved_texts, question, ragas_llm)
            if ragas_f is not None:
                row["ragas_faithfulness"] = round(ragas_f, 3)

        results.append(row)

    return results


def aggregate(results: List[Dict[str, Any]]) -> Dict[str, float]:
    numeric_keys = [
        "answer_relevancy",
        "context_precision",
        "context_recall",
        "answer_correctness_rouge",
        "citation_rate",
        "mean_citation_groundedness",
        "citation_resolution_rate",
        "nli_faithfulness",
        "truthfulness_score",
        "ragas_faithfulness",
    ]
    agg: Dict[str, float] = {}
    for k in numeric_keys:
        vals = [r[k] for r in results if k in r]
        if vals:
            agg[f"mean_{k}"] = round(sum(vals) / len(vals), 3)
    return agg


def write_report(
    results: List[Dict[str, Any]],
    agg: Dict[str, float],
    output_dir: str,
    thresholds: Dict[str, float],
) -> bool:
    """Write JSON + Markdown report. Returns True if all thresholds pass."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    report = {"timestamp": ts, "summary": agg, "per_question": results}
    json_path = out / f"report-{ts}.json"
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2)
    logger.info("JSON report: %s", json_path)

    # Markdown report
    md_lines = [
        f"# Evaluation Report — {ts}",
        "",
        "## Summary",
        "",
        "| Metric | Score |",
        "|--------|-------|",
    ]
    for k, v in sorted(agg.items()):
        md_lines.append(f"| {k} | {v:.3f} |")

    failures = {k: v for k, v in thresholds.items() if agg.get(f"mean_{k}", 1.0) < v}
    if failures:
        md_lines += ["", "## Threshold Failures", ""]
        for k, threshold in failures.items():
            actual = agg.get(f"mean_{k}", 0.0)
            md_lines.append(f"- **{k}**: {actual:.3f} < required {threshold:.3f}")

    md_lines += ["", "## Per-Question Results", ""]
    for r in results:
        md_lines.append(f"### {r['question'][:80]}")
        md_lines.append(f"**Answer:** {r['answer'][:200]}")
        score_parts = []
        for k in ("nli_faithfulness", "ragas_faithfulness", "answer_relevancy", "answer_correctness_rouge", "citation_rate"):
            if k in r:
                score_parts.append(f"{k}={r[k]:.3f}")
        md_lines.append(f"**Scores:** {' | '.join(score_parts)}")
        md_lines.append("")

    md_path = out / f"report-{ts}.md"
    with open(md_path, "w") as f:
        f.write("\n".join(md_lines))
    logger.info("Markdown report: %s", md_path)

    return not failures


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the RAG pipeline on a golden dataset")
    parser.add_argument("--dataset", required=True, help="Path to JSONL dataset")
    parser.add_argument("--judge-provider", default=None, help="LLM provider for RAGAS judge (e.g. ollama)")
    parser.add_argument("--judge-model", default=None, help="Model for RAGAS judge")
    parser.add_argument("--output", default="evals/reports", help="Output directory for reports")
    parser.add_argument("--mock", action="store_true", help="Use mock pipeline (no LLM required)")
    parser.add_argument("--no-nli", action="store_true", help="Skip NLI faithfulness scoring")
    parser.add_argument(
        "--force-nli",
        action="store_true",
        help="Run offline NLI even when evaluation.inline_enabled is false",
    )
    parser.add_argument("--faithfulness-threshold", type=float, default=0.5, help="Min mean NLI faithfulness")
    parser.add_argument("--correctness-threshold", type=float, default=0.2, help="Min mean answer_correctness_rouge")
    args = parser.parse_args()

    samples = load_dataset(args.dataset)
    logger.info("Loaded %d samples from %s", len(samples), args.dataset)

    if args.mock:
        pipeline: Any = MockPipeline()
    else:
        provider = args.judge_provider or "ollama"
        pipeline = LivePipeline(provider=provider, model=args.judge_model)

    # Optional RAGAS LLM judge
    ragas_llm = None
    if args.judge_provider and not args.mock:
        try:
            from src.core.llm_provider import LLMProviderRouter
            from src.utils.config import load_config
            from evals.adapters.ragas_llm_adapter import make_ragas_llm

            cfg = load_config("config.yaml")
            router = LLMProviderRouter(cfg.llm)
            model = args.judge_model or cfg.llm.default_model_by_provider.get(args.judge_provider, "")
            ragas_llm = make_ragas_llm(router, args.judge_provider, model)
            logger.info("RAGAS judge: %s/%s", args.judge_provider, model)
        except ImportError:
            logger.info("ragas/langchain-core not installed — skipping RAGAS metrics. Install requirements/eval.txt.")

    # Optional NLI scorer
    faithfulness_scorer = None
    if not args.no_nli:
        try:
            from src.utils.config import load_config
            from src.evaluation.truthfulness import TruthfulnessScorer

            cfg = load_config("config.yaml")
            if cfg.evaluation.inline_enabled or args.force_nli:
                faithfulness_scorer = TruthfulnessScorer()
                logger.info("NLI faithfulness scorer loaded")
            else:
                logger.info("Skipping NLI scorer because evaluation.inline_enabled=false (use --force-nli to override)")
        except Exception as exc:
            logger.warning("NLI scorer unavailable: %s", exc)

    results = evaluate_dataset(samples, pipeline, ragas_llm=ragas_llm, faithfulness_scorer=faithfulness_scorer)
    agg = aggregate(results)

    logger.info("Aggregate scores: %s", json.dumps(agg, indent=2))

    thresholds = {
        "nli_faithfulness": args.faithfulness_threshold,
        "answer_correctness_rouge": args.correctness_threshold,
    }
    passed = write_report(results, agg, args.output, thresholds)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
