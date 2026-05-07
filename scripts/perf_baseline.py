"""Lightweight local API load baseline using FastAPI TestClient."""

from __future__ import annotations

import statistics
import time
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from src.api import main as api_main
from src.api.main import app
from src.core.rag_orchestrator import QueryResponse


def _fake_run(_req):
    return QueryResponse(
        query="q",
        provider="ollama",
        model="qwen2.5:7b",
        answer="ok",
        processing_time_ms=15.0,
    )


def _single_call(client: TestClient) -> float:
    t0 = time.perf_counter()
    resp = client.post("/query", json={"query": "benchmark"})
    resp.raise_for_status()
    return (time.perf_counter() - t0) * 1000.0


def main() -> None:
    api_main._orchestrator.run = _fake_run
    client = TestClient(app)
    total_requests = 200
    concurrency = 20
    samples = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(_single_call, client) for _ in range(total_requests)]
        for f in futures:
            samples.append(f.result())

    p95 = statistics.quantiles(samples, n=100)[94]
    avg = statistics.mean(samples)
    print(f"requests={total_requests}")
    print(f"concurrency={concurrency}")
    print(f"latency_ms_avg={avg:.2f}")
    print(f"latency_ms_p95={p95:.2f}")


if __name__ == "__main__":
    main()
