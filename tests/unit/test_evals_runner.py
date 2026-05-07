"""Unit tests for the offline eval harness (evals/run_evals.py).

All tests use MockPipeline so no real LLM, vector store, or NLI model is needed.
"""

from __future__ import annotations

import json

import pytest
from evals.run_evals import (
    MockPipeline,
    aggregate,
    answer_correctness_rouge,
    answer_relevancy,
    citation_rate,
    citation_resolution_rate,
    context_precision_at_k,
    context_recall,
    evaluate_dataset,
    load_dataset,
    write_report,
)

# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------

def test_load_dataset_valid(tmp_path):
    p = tmp_path / "test.jsonl"
    p.write_text('{"user_input": "What is RAG?", "reference": "RAG is ...", "reference_contexts": []}\n')
    data = load_dataset(str(p))
    assert len(data) == 1
    assert data[0]["user_input"] == "What is RAG?"


def test_load_dataset_empty(tmp_path):
    p = tmp_path / "empty.jsonl"
    p.write_text("")
    with pytest.raises(ValueError, match="empty"):
        load_dataset(str(p))


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def test_answer_relevancy_identical():
    # Identical question and answer should score close to 1.0
    score = answer_relevancy("What is RAG?", "What is RAG?")
    assert score >= 0.9


def test_answer_relevancy_unrelated():
    score = answer_relevancy("What is RAG?", "Cats enjoy sleeping in sunlight.")
    assert score < 0.7


def test_context_precision_exact_match():
    retrieved = ["RAG combines retrieval and generation to produce grounded answers."]
    refs = ["RAG combines retrieval and generation."]
    precision = context_precision_at_k(retrieved, refs)
    assert precision == 1.0


def test_context_precision_no_match():
    retrieved = ["Cats are fluffy."]
    refs = ["RAG combines retrieval and generation."]
    precision = context_precision_at_k(retrieved, refs)
    assert precision == 0.0


def test_context_recall_full():
    retrieved = ["RAG combines retrieval and generation to produce grounded answers."]
    refs = ["RAG combines retrieval and generation."]
    recall = context_recall(retrieved, refs)
    assert recall == 1.0


def test_context_recall_empty_refs():
    assert context_recall(["some chunk"], []) == 1.0


def test_answer_correctness_rouge_similar():
    ans = "RAG stands for Retrieval Augmented Generation."
    ref = "RAG stands for Retrieval-Augmented Generation."
    score = answer_correctness_rouge(ans, ref)
    assert score > 0.5


def test_answer_correctness_rouge_unrelated():
    ans = "Cats are fluffy."
    ref = "RAG stands for Retrieval Augmented Generation."
    score = answer_correctness_rouge(ans, ref)
    assert score < 0.3


# ---------------------------------------------------------------------------
# MockPipeline
# ---------------------------------------------------------------------------

def test_mock_pipeline_rag():
    pipeline = MockPipeline()
    result = pipeline.run("What is RAG?")
    assert "rag" in result["answer"].lower() or "retrieval" in result["answer"].lower()
    assert isinstance(result["citations"], list)
    assert isinstance(result["retrieved"], list)


def test_mock_pipeline_unknown():
    pipeline = MockPipeline()
    result = pipeline.run("Tell me about quantum entanglement")
    assert isinstance(result["answer"], str)


# ---------------------------------------------------------------------------
# evaluate_dataset
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_dataset():
    return [
        {
            "user_input": "What is RAG?",
            "reference": "RAG stands for Retrieval-Augmented Generation.",
            "reference_contexts": ["Retrieval-Augmented Generation combines retrieval with LLM generation."],
        },
        {
            "user_input": "What is BM25?",
            "reference": "BM25 is a ranking function for information retrieval.",
            "reference_contexts": ["BM25 is a probabilistic ranking function used in information retrieval."],
        },
    ]


def test_evaluate_dataset_with_mock(sample_dataset):
    pipeline = MockPipeline()
    results = evaluate_dataset(sample_dataset, pipeline)
    assert len(results) == 2
    for r in results:
        assert "question" in r
        assert "answer" in r
        assert "answer_relevancy" in r
        assert "context_precision" in r
        assert "context_recall" in r
        assert "answer_correctness_rouge" in r
        assert "citation_resolution_rate" in r
        assert "nli_source_mode" in r
        assert 0.0 <= r["answer_relevancy"] <= 1.0


def test_aggregate_all_fields(sample_dataset):
    pipeline = MockPipeline()
    results = evaluate_dataset(sample_dataset, pipeline)
    agg = aggregate(results)
    assert "mean_answer_relevancy" in agg
    assert "mean_answer_correctness_rouge" in agg
    assert "mean_citation_resolution_rate" in agg
    for v in agg.values():
        assert 0.0 <= v <= 1.0


def test_citation_rate_supported_only():
    citations = [
        {"resolved": True, "verification": "weak_support", "verification_score": 0.8},
        {"resolved": True, "verification": "supported", "verification_score": 0.9},
    ]
    assert citation_rate(citations) == 1.0


def test_citation_resolution_rate_tracks_resolved():
    citations = [{"resolved": False}, {"resolved": True}]
    assert citation_resolution_rate(citations) == 1.0


def test_evaluate_dataset_includes_truthfulness_fields():
    class FakeScorer:
        def score(self, _answer, _sources, _citations):
            class _Result:
                nli_faithfulness = 0.9
                citation_groundedness = 0.8
                uncited_claims = 1
                score = 0.86

            return _Result()

    pipeline = MockPipeline()
    sample = [{"user_input": "What is RAG?", "reference": "RAG.", "reference_contexts": []}]
    rows = evaluate_dataset(sample, pipeline, faithfulness_scorer=FakeScorer())
    assert rows[0]["nli_faithfulness"] == 0.9
    assert rows[0]["citation_groundedness"] == 0.8
    assert rows[0]["uncited_claims"] == 1
    assert rows[0]["score"] == 0.86


# ---------------------------------------------------------------------------
# write_report
# ---------------------------------------------------------------------------

def test_write_report_creates_files(tmp_path, sample_dataset):
    pipeline = MockPipeline()
    results = evaluate_dataset(sample_dataset, pipeline)
    agg = aggregate(results)
    passed = write_report(results, agg, str(tmp_path), {})
    assert passed is True
    json_files = list(tmp_path.glob("*.json"))
    md_files = list(tmp_path.glob("*.md"))
    assert len(json_files) == 1
    assert len(md_files) == 1

    with open(json_files[0]) as f:
        report = json.load(f)
    assert "summary" in report
    assert "per_question" in report


def test_write_report_threshold_failure(tmp_path, sample_dataset):
    pipeline = MockPipeline()
    results = evaluate_dataset(sample_dataset, pipeline)
    agg = aggregate(results)
    # Set an impossible threshold
    passed = write_report(results, agg, str(tmp_path), {"answer_relevancy": 999.0})
    assert passed is False
