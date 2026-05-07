# Phase 4 API Baseline

This baseline measures API framework overhead using the local FastAPI app with a stubbed orchestrator response.

## Command

`PYTHONPATH=. .venv/bin/python scripts/perf_baseline.py`

## Results

- requests: 200
- concurrency: 20
- average latency: 14.91 ms
- p95 latency: 19.54 ms

## Notes

- This is not end-to-end RAG latency because retrieval and LLM generation are mocked.
- Use this baseline to separate framework overhead from model/runtime latency when running full-load tests.
