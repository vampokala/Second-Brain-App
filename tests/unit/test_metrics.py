"""Unit tests for metrics collector."""

from datetime import datetime

from src.monitoring.metrics import MetricsCollector, RequestMetrics, init_metrics_collector


def test_metrics_collector_records_request():
    """Verify collector records request metrics."""
    collector = MetricsCollector(window_size=100)

    metrics = RequestMetrics(
        request_id="req-1",
        total_latency_ms=1000.0,
        retrieval_latency_ms=200.0,
        reranking_latency_ms=150.0,
        generation_latency_ms=600.0,
        citation_latency_ms=50.0,
        truthfulness_latency_ms=20.0,
        cost_usd=0.005,
        citation_groundedness=0.92,
        nli_faithfulness=0.88,
        uncited_claims=0,
        timestamp=datetime.utcnow().isoformat(),
    )

    collector.record_request(metrics)
    assert len(collector.metrics) == 1


def test_metrics_percentile_calculation():
    """Verify P50, P95, P99 calculations."""
    collector = MetricsCollector(window_size=100)

    # Record 100 requests with latencies 100-1000ms
    for i in range(1, 101):
        metrics = RequestMetrics(
            request_id=f"req-{i}",
            total_latency_ms=float(i * 10),
            retrieval_latency_ms=100.0,
            reranking_latency_ms=50.0,
            generation_latency_ms=float(i * 5),
            citation_latency_ms=10.0,
            truthfulness_latency_ms=5.0,
            cost_usd=0.01,
            citation_groundedness=0.90,
            nli_faithfulness=0.90,
            uncited_claims=0,
            timestamp=datetime.utcnow().isoformat(),
        )
        collector.record_request(metrics)

    # Check percentiles
    p50 = collector.get_percentile("total_latency_ms", 50)
    p95 = collector.get_percentile("total_latency_ms", 95)
    p99 = collector.get_percentile("total_latency_ms", 99)

    assert p50 is not None
    assert p95 is not None and p95 >= p50
    assert p99 is not None and p99 >= p95


def test_dashboard_metrics_aggregation():
    """Verify dashboard metrics aggregation."""
    collector = MetricsCollector(window_size=10)

    for i in range(5):
        metrics = RequestMetrics(
            request_id=f"req-{i}",
            total_latency_ms=1000.0,
            retrieval_latency_ms=200.0,
            reranking_latency_ms=150.0,
            generation_latency_ms=600.0,
            citation_latency_ms=50.0,
            truthfulness_latency_ms=25.0,
            cost_usd=0.005,
            citation_groundedness=0.92,
            nli_faithfulness=0.88,
            uncited_claims=0,
            timestamp=datetime.utcnow().isoformat(),
        )
        collector.record_request(metrics)

    dashboard = collector.get_dashboard_metrics()

    assert dashboard["summary"]["total_requests"] == 5
    assert "latency" in dashboard
    assert "cost" in dashboard
    assert "quality" in dashboard
    assert dashboard["latency"]["total_p50_ms"] > 0
    assert dashboard["latency"]["truthfulness_avg_ms"] == 25.0
    assert "truthfulness" in dashboard["latency"]["breakdown_pct"]


def test_dashboard_no_data():
    """Verify dashboard handles no data gracefully."""
    collector = MetricsCollector(window_size=10)
    dashboard = collector.get_dashboard_metrics()

    assert dashboard["status"] == "no_data"
    assert "message" in dashboard


def test_metrics_rolling_window():
    """Verify rolling window discards old metrics."""
    collector = MetricsCollector(window_size=5)

    for i in range(10):
        metrics = RequestMetrics(
            request_id=f"req-{i}",
            total_latency_ms=1000.0 + i,
            retrieval_latency_ms=200.0,
            reranking_latency_ms=150.0,
            generation_latency_ms=600.0,
            citation_latency_ms=50.0,
            truthfulness_latency_ms=None,
            cost_usd=0.005,
            citation_groundedness=0.92,
            nli_faithfulness=0.88,
            uncited_claims=0,
            timestamp=datetime.utcnow().isoformat(),
        )
        collector.record_request(metrics)

    # Should only keep last 5
    assert len(collector.metrics) == 5


def test_metrics_collector_singleton():
    """Verify singleton pattern works."""
    init_metrics_collector(window_size=100)
    from src.monitoring.metrics import get_metrics_collector

    collector1 = get_metrics_collector()
    collector2 = get_metrics_collector()
    assert collector1 is collector2


def test_dashboard_ignores_missing_step_latency():
    collector = MetricsCollector(window_size=10)
    collector.record_request(
        RequestMetrics(
            request_id="cache-hit",
            total_latency_ms=50.0,
            retrieval_latency_ms=None,
            reranking_latency_ms=None,
            generation_latency_ms=None,
            citation_latency_ms=None,
            truthfulness_latency_ms=None,
            cost_usd=0.0,
            citation_groundedness=0.0,
            nli_faithfulness=0.0,
            uncited_claims=0,
            timestamp=datetime.utcnow().isoformat(),
            cached=True,
        )
    )
    dashboard = collector.get_dashboard_metrics()
    assert dashboard["latency"]["truthfulness_avg_ms"] == 0.0
