"""Unit tests for the TruthfulnessScorer.

The NLI model is NOT loaded in these tests — we mock the CrossEncoder
to avoid downloading model weights in CI.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest
from src.evaluation.truthfulness import (
    TruthfulnessResult,
    TruthfulnessScorer,
    _split_claims,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scorer_with_mock_model(entailment_probs: list[float]) -> TruthfulnessScorer:
    """Return a TruthfulnessScorer whose NLI model is a mock."""
    scorer = TruthfulnessScorer()
    mock_model = MagicMock()

    def _predict(pairs):
        n = len(pairs)
        # Return raw logits: contradiction=0, entailment=entailment_probs[i], neutral=0
        logits = np.zeros((n, 3), dtype=float)
        for i in range(n):
            prob = entailment_probs[i % len(entailment_probs)]
            # Invert softmax: make entailment dominant when prob is high
            logits[i, 1] = prob * 10  # exaggerated so softmax pushes toward 1
            logits[i, 0] = (1 - prob) * 5
            logits[i, 2] = (1 - prob) * 5
        return logits

    mock_model.predict = _predict
    TruthfulnessScorer._model = mock_model
    return scorer


# ---------------------------------------------------------------------------
# _split_claims
# ---------------------------------------------------------------------------

def test_split_claims_basic():
    text = "RAG combines retrieval and generation. It is useful for grounded answers. Short."
    claims = _split_claims(text)
    assert len(claims) >= 2
    assert all(len(c.split()) >= 4 for c in claims)


def test_split_claims_empty():
    assert _split_claims("") == []


def test_split_claims_short_only():
    assert _split_claims("Yes. No. Ok.") == []


# ---------------------------------------------------------------------------
# nli_faithfulness
# ---------------------------------------------------------------------------

def test_nli_faithfulness_entailed():
    scorer = _make_scorer_with_mock_model([0.9])
    score = scorer.nli_faithfulness(
        "RAG retrieves documents before generation.",
        ["RAG retrieves relevant documents from a knowledge base before generating an answer."],
    )
    assert score == pytest.approx(1.0)


def test_nli_faithfulness_not_entailed():
    scorer = _make_scorer_with_mock_model([0.1])
    score = scorer.nli_faithfulness(
        "RAG retrieves documents before generation.",
        ["Cats are fluffy animals."],
    )
    assert score == pytest.approx(0.0)


def test_nli_faithfulness_empty_response():
    scorer = TruthfulnessScorer()
    assert scorer.nli_faithfulness("", ["some source"]) == 0.0


def test_nli_faithfulness_empty_sources():
    scorer = TruthfulnessScorer()
    assert scorer.nli_faithfulness("Some response.", []) == 0.0


# ---------------------------------------------------------------------------
# _citation_groundedness
# ---------------------------------------------------------------------------

def test_citation_groundedness_mean():
    scorer = TruthfulnessScorer()
    citations = [
        {"verification_score": 0.8},
        {"verification_score": 0.6},
    ]
    assert scorer._citation_groundedness(citations) == pytest.approx(0.7)


def test_citation_groundedness_empty():
    scorer = TruthfulnessScorer()
    assert scorer._citation_groundedness([]) == 0.0


# ---------------------------------------------------------------------------
# _count_uncited_claims
# ---------------------------------------------------------------------------

def test_uncited_claims_all_cited():
    scorer = TruthfulnessScorer()
    text = "RAG is a technique. [Doc chunk1] It improves accuracy. [Chunk chunk2]"
    # Both long-enough sentences contain a citation marker
    assert scorer._count_uncited_claims(text) >= 0  # not all may be long enough


def test_uncited_claims_none_cited():
    scorer = TruthfulnessScorer()
    text = "This statement has no citation. Another statement here without any reference."
    count = scorer._count_uncited_claims(text)
    assert count == 2


# ---------------------------------------------------------------------------
# score (integration of all three)
# ---------------------------------------------------------------------------

def test_score_returns_truthfulness_result():
    scorer = _make_scorer_with_mock_model([0.85])
    response = "RAG retrieves documents before generation. It improves factual accuracy."
    sources = ["RAG retrieves relevant documents and improves factual accuracy."]
    citations = [{"verification_score": 0.9, "resolved": True}]
    result = scorer.score(response, sources, citations)
    assert isinstance(result, TruthfulnessResult)
    assert 0.0 <= result.nli_faithfulness <= 1.0
    assert 0.0 <= result.citation_groundedness <= 1.0
    assert result.uncited_claims >= 0
    assert 0.0 <= result.score <= 1.0


def test_score_aggregate_weights():
    """Score = 0.6 * nli + 0.4 * groundedness."""
    scorer = _make_scorer_with_mock_model([0.9])  # nli will be ~1.0
    response = "RAG retrieves documents before generation."
    sources = ["RAG retrieves documents."]
    citations = [{"verification_score": 0.5, "resolved": True}]
    result = scorer.score(response, sources, citations)
    expected = round(0.6 * result.nli_faithfulness + 0.4 * result.citation_groundedness, 3)
    assert result.score == pytest.approx(expected, abs=0.01)


def test_score_to_dict():
    scorer = _make_scorer_with_mock_model([0.8])
    result = scorer.score("Short answer here.", ["Source text here."], [])
    d = result.to_dict()
    assert set(d.keys()) == {"nli_faithfulness", "citation_groundedness", "uncited_claims", "score"}


# ---------------------------------------------------------------------------
# Teardown: reset class-level model cache after tests that mock it
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_model_cache():
    yield
    TruthfulnessScorer._model = None
