import json
import os

import pytest
from src.evaluation.retrieval_metrics import (
    evaluate_all,
    f1_at_k,
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)


@pytest.fixture
def toy_qrels():
    path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "qrels.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {q: set(ids) for q, ids in data["qrels"].items()}


def test_precision_recall_f1(toy_qrels):
    ranked = {"q1": ["doc_x", "doc_a", "doc_b"], "q2": ["doc_c", "doc_x"]}
    assert precision_at_k(ranked["q1"], toy_qrels["q1"], k=3) == pytest.approx(2 / 3)
    assert recall_at_k(ranked["q1"], toy_qrels["q1"], k=3) == 1.0
    assert f1_at_k(ranked["q1"], toy_qrels["q1"], k=3) == pytest.approx(4 / 5)


def test_mrr_and_evaluate_all(toy_qrels):
    ranked = {"q1": ["doc_x", "doc_a"], "q2": ["doc_x", "doc_c"]}
    assert mean_reciprocal_rank(ranked, toy_qrels) == pytest.approx((0.5 + 0.5) / 2)
    agg = evaluate_all(ranked, toy_qrels, k_values=(1, 3))
    assert "precision@1" in agg
    assert "mrr" in agg


def test_ndcg():
    graded = {"doc_a": 2.0, "doc_b": 1.0, "doc_x": 0.0}
    ranked = ["doc_x", "doc_a", "doc_b"]
    assert ndcg_at_k(ranked, graded, k=3) <= 1.0
    assert ndcg_at_k(["doc_a", "doc_b", "doc_x"], graded, k=3) >= ndcg_at_k(ranked, graded, k=3)


def test_reciprocal_rank_single_query():
    assert reciprocal_rank(["a", "b", "c"], {"b"}) == pytest.approx(0.5)
