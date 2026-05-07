"""
Metrics collection and aggregation for RAG pipeline.
Tracks latency percentiles, cost, retrieval precision, citation accuracy.
"""

import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class StepMetrics:
    """Metrics for a single RAG pipeline step."""

    step_name: str  # "retrieval", "reranking", "generation", "citations", "truthfulness"
    latency_ms: float
    timestamp: str
    metadata: Dict = field(default_factory=dict)  # Provider, model, token counts, etc.


@dataclass
class RequestMetrics:
    """Aggregated metrics for a single query request."""

    request_id: str
    total_latency_ms: float
    retrieval_latency_ms: Optional[float]
    reranking_latency_ms: Optional[float]
    generation_latency_ms: Optional[float]
    citation_latency_ms: Optional[float]
    truthfulness_latency_ms: Optional[float]

    # Cost
    cost_usd: float

    # Quality (online signals — computable without ground truth)
    citation_groundedness: float
    nli_faithfulness: float
    uncited_claims: int
    timestamp: str
    cached: bool = False


class MetricsCollector:
    """
    In-memory metrics collector with time-windowed aggregation.

    Stores metrics in a rolling window (default 1000 last requests).
    Computes P50, P95, P99 latencies and cost trends.

    NOTE: This replaces src/utils/log.py's MetricsCollector.
    """

    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.metrics: deque = deque(maxlen=window_size)
        self.lock = threading.RLock()

    def record_request(self, metrics: RequestMetrics):
        """Record a completed request's metrics."""
        with self.lock:
            self.metrics.append(metrics)

    def get_percentile(
        self, metric_field: str, percentile: float
    ) -> Optional[float]:
        """
        Get percentile value for a metric field.

        Args:
            metric_field: e.g., "total_latency_ms", "cost_usd"
            percentile: 0-100, e.g., 50 for P50, 95 for P95

        Returns:
            Percentile value or None if insufficient data
        """
        with self.lock:
            if not self.metrics:
                return None

            values = sorted([getattr(m, metric_field) for m in self.metrics])
            idx = int(len(values) * percentile / 100)
            return values[min(idx, len(values) - 1)]

    def get_dashboard_metrics(self) -> Dict:
        """
        Return aggregated metrics suitable for dashboarding.
        """
        with self.lock:
            if not self.metrics:
                return {
                    "status": "no_data",
                    "message": "No requests recorded yet",
                }

            metrics_list = list(self.metrics)
            n = len(metrics_list)

            # Latency percentiles (ms)
            latency_p50 = self.get_percentile("total_latency_ms", 50)
            latency_p95 = self.get_percentile("total_latency_ms", 95)
            latency_p99 = self.get_percentile("total_latency_ms", 99)

            # Step-wise latencies (average)
            def _avg_optional(field: str) -> float:
                vals = [getattr(m, field) for m in metrics_list if getattr(m, field) is not None]
                if not vals:
                    return 0.0
                return sum(vals) / len(vals)

            retrieval_avg = _avg_optional("retrieval_latency_ms")
            reranking_avg = _avg_optional("reranking_latency_ms")
            generation_avg = _avg_optional("generation_latency_ms")
            citation_avg = _avg_optional("citation_latency_ms")
            truthfulness_avg = _avg_optional("truthfulness_latency_ms")

            # Cost
            cost_total = sum(m.cost_usd for m in metrics_list)
            cost_avg = cost_total / n
            cost_p95 = self.get_percentile("cost_usd", 95)

            # Quality
            groundedness_values = [m.citation_groundedness for m in metrics_list if m.citation_groundedness > 0]
            faithfulness_values = [m.nli_faithfulness for m in metrics_list if m.nli_faithfulness > 0]

            groundedness_avg = (
                sum(groundedness_values) / len(groundedness_values)
                if groundedness_values
                else 0.0
            )
            faithfulness_avg = (
                sum(faithfulness_values) / len(faithfulness_values)
                if faithfulness_values
                else 0.0
            )

            # Breakdown percentages
            total_step_latency = retrieval_avg + reranking_avg + generation_avg + citation_avg + truthfulness_avg
            if total_step_latency > 0:
                breakdown_pct = {
                    "retrieval": round(retrieval_avg / total_step_latency * 100, 1),
                    "reranking": round(reranking_avg / total_step_latency * 100, 1),
                    "generation": round(generation_avg / total_step_latency * 100, 1),
                    "citation": round(citation_avg / total_step_latency * 100, 1),
                    "truthfulness": round(truthfulness_avg / total_step_latency * 100, 1),
                }
            else:
                breakdown_pct = {
                    "retrieval": 0.0,
                    "reranking": 0.0,
                    "generation": 0.0,
                    "citation": 0.0,
                    "truthfulness": 0.0,
                }

            return {
                "summary": {
                    "total_requests": n,
                    "window_size": self.window_size,
                    "last_updated": datetime.utcnow().isoformat(),
                },
                "latency": {
                    "total_p50_ms": round(latency_p50, 2) if latency_p50 else 0.0,
                    "total_p95_ms": round(latency_p95, 2) if latency_p95 else 0.0,
                    "total_p99_ms": round(latency_p99, 2) if latency_p99 else 0.0,
                    "retrieval_avg_ms": round(retrieval_avg, 2),
                    "reranking_avg_ms": round(reranking_avg, 2),
                    "generation_avg_ms": round(generation_avg, 2),
                    "citation_avg_ms": round(citation_avg, 2),
                    "truthfulness_avg_ms": round(truthfulness_avg, 2),
                    "breakdown_pct": breakdown_pct,
                },
                "cost": {
                    "total_usd": round(cost_total, 4),
                    "avg_per_request_usd": round(cost_avg, 6),
                    "p95_per_request_usd": round(cost_p95, 6) if cost_p95 else 0.0,
                },
                "quality": {
                    "citation_groundedness_avg": round(groundedness_avg, 3),
                    "nli_faithfulness_avg": round(faithfulness_avg, 3),
                },
            }


# Global metrics collector instance
_collector_instance: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Singleton getter."""
    global _collector_instance
    if _collector_instance is None:
        _collector_instance = MetricsCollector()
    return _collector_instance


def init_metrics_collector(window_size: int = 1000) -> MetricsCollector:
    """Initialize the metrics collector (useful for testing)."""
    global _collector_instance
    _collector_instance = MetricsCollector(window_size=window_size)
    return _collector_instance
