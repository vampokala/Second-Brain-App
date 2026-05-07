"""Unit tests for regression gate script."""

import os
import sys

# Add scripts to path for import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../scripts"))
from compare_evals import compare_metrics


def test_no_regression_when_metrics_stable():
    """Verify no regression when metrics are unchanged."""
    baseline = {
        "latency": {"total_p50_ms": 1000.0, "retrieval_avg_ms": 200.0},
        "quality": {"citation_groundedness_avg": 0.92},
        "cost": {"avg_per_request_usd": 0.005},
    }
    current = baseline.copy()

    passed, results = compare_metrics(baseline, current, threshold_pct=5.0)

    assert passed is True
    assert len(results["regressions"]) == 0


def test_regression_detected_for_latency_increase():
    """Verify regression detected when latency increases >threshold."""
    baseline = {
        "latency": {"total_p50_ms": 1000.0},
        "quality": {},
        "cost": {},
    }
    current = {
        "latency": {"total_p50_ms": 1100.0},  # 10% increase
        "quality": {},
        "cost": {},
    }

    passed, results = compare_metrics(baseline, current, threshold_pct=5.0)

    assert passed is False
    assert len(results["regressions"]) == 1
    assert results["regressions"][0]["metric"] == "total_p50_ms"
    assert results["regressions"][0]["pct_change"] > 5.0


def test_no_regression_when_quality_improves():
    """Verify no regression when quality improves."""
    baseline = {
        "latency": {},
        "quality": {"citation_groundedness_avg": 0.90},
        "cost": {},
    }
    current = {
        "latency": {},
        "quality": {"citation_groundedness_avg": 0.95},  # Improvement
        "cost": {},
    }

    passed, results = compare_metrics(baseline, current, threshold_pct=5.0)

    assert passed is True
    assert len(results["regressions"]) == 0


def test_regression_detected_for_quality_decrease():
    """Verify regression detected when quality decreases >threshold."""
    baseline = {
        "latency": {},
        "quality": {"nli_faithfulness_avg": 0.90},
        "cost": {},
    }
    current = {
        "latency": {},
        "quality": {"nli_faithfulness_avg": 0.80},  # 11% decrease
        "cost": {},
    }

    passed, results = compare_metrics(baseline, current, threshold_pct=5.0)

    assert passed is False
    assert len(results["regressions"]) == 1
    assert results["regressions"][0]["metric"] == "nli_faithfulness_avg"


def test_regression_detected_for_cost_increase():
    """Verify regression detected when cost increases >threshold."""
    baseline = {
        "latency": {},
        "quality": {},
        "cost": {"avg_per_request_usd": 0.005},
    }
    current = {
        "latency": {},
        "quality": {},
        "cost": {"avg_per_request_usd": 0.0055},  # 10% increase
    }

    passed, results = compare_metrics(baseline, current, threshold_pct=5.0)

    assert passed is False
    assert len(results["regressions"]) == 1
    assert results["regressions"][0]["metric"] == "avg_per_request_usd"


def test_no_regression_with_generous_threshold():
    """Verify no regression when change is below threshold."""
    baseline = {
        "latency": {"total_p50_ms": 1000.0},
        "quality": {},
        "cost": {},
    }
    current = {
        "latency": {"total_p50_ms": 1040.0},  # 4% increase
        "quality": {},
        "cost": {},
    }

    passed, results = compare_metrics(baseline, current, threshold_pct=5.0)

    assert passed is True
    assert len(results["regressions"]) == 0


def test_multiple_regressions_detected():
    """Verify multiple regressions are all detected."""
    baseline = {
        "latency": {
            "total_p50_ms": 1000.0,
            "total_p95_ms": 2000.0,
        },
        "quality": {"citation_groundedness_avg": 0.90},
        "cost": {},
    }
    current = {
        "latency": {
            "total_p50_ms": 1100.0,  # 10% increase
            "total_p95_ms": 2200.0,  # 10% increase
        },
        "quality": {"citation_groundedness_avg": 0.80},  # 11% decrease
        "cost": {},
    }

    passed, results = compare_metrics(baseline, current, threshold_pct=5.0)

    assert passed is False
    assert len(results["regressions"]) == 3
    assert all(r["pct_change"] > 5.0 for r in results["regressions"])


def test_missing_metrics_are_skipped():
    """Verify missing metrics in baseline/current are skipped."""
    baseline = {
        "latency": {"total_p50_ms": 1000.0},
        "quality": {},
        "cost": {},
    }
    current = {
        "latency": {"total_p95_ms": 2000.0},  # Different metric
        "quality": {},
        "cost": {},
    }

    passed, results = compare_metrics(baseline, current, threshold_pct=5.0)

    # No common metrics to compare, so no regressions
    assert passed is True
    assert len(results["regressions"]) == 0
