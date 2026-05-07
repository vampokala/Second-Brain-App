# Phase 5: Production Monitoring & Observability

**Timeline:** 3 weeks  
**Status:** Complete  
**Owner:** Vamshi Pokala

## Overview

Phase 5 hardens the doc-ingestion RAG system for production through:

1. **Distributed tracing** (LangFuse) for end-to-end pipeline visibility
2. **Latency profiling** (P50, P95, P99) per step
3. **Cost tracking** (USD per request)
4. **Real-time metrics dashboard** at `/observability/dashboard`
5. **Regression gating** (GitHub Actions) to prevent accuracy degradation on PRs
6. **Citation accuracy monitoring** (groundedness, coverage trends)

## Architecture

### Tracing Flow
```
User Query
    ↓
[LangFuse Trace Start]
    ↓
Retrieval (BM25 + Vector)
[TRACE: latency, chunks retrieved, scores]
    ↓
Reranking (Cross-Encoder)
[TRACE: latency, input/output chunks]
    ↓
Generation (LLM)
[TRACE: latency, tokens, cost, provider]
    ↓
Citation Verification
[TRACE: latency, citations verified]
    ↓
[Flush to LangFuse]
    ↓
Response + Metrics Recorded
```

### Metrics Aggregation
```
Per-Request Metrics (RequestMetrics)
    ↓
In-Memory Collector (1000 rolling window)
    ↓
Dashboard Endpoint (/observability/dashboard)
    ↓
JSON: P50/P95/P99 latencies, cost trends, quality scores
```

### Regression Gating
```
PR Submitted
    ↓
GitHub Actions: Run evals on golden dataset
    ↓
Compare against baseline (main branch)
    ↓
Check: Latency increase <5%? Quality decrease <5%?
    ↓
If FAIL: Block PR + comment with regression details
If PASS: Allow merge
```

## Key Components

### 1. Observability Module (`src/core/observability.py`)

**Provides:**
- `RAGObserver` class with step-level tracing context managers
- LangFuse client integration
- No-op when disabled (useful for demo mode)
- Background-safe async flush

**Usage:**
```python
observer = get_observer()

# One trace per request, spans as children
with observer.trace_request("rag_query", query=query_text) as trace:
    with observer.trace_step(trace, "retrieval") as s:
        result = retriever.retrieve(query)
        s["chunks_retrieved"] = len(result)
    with observer.trace_step(trace, "generation", {"provider": provider}) as s:
        answer = generator.generate(query, result)

observer.flush_async()  # non-blocking
```

### 2. Metrics Collector (`src/monitoring/metrics.py`)

**Provides:**
- `MetricsCollector` for in-memory aggregation
- Percentile calculations (P50, P95, P99)
- Dashboard-friendly JSON aggregations
- Thread-safe recording

**Metrics tracked:**
```
Latency:
- total_latency_ms (P50, P95, P99)
- retrieval_avg_ms
- reranking_avg_ms
- generation_avg_ms
- citation_avg_ms
- Breakdown percentages

Cost:
- total_usd (across all requests)
- avg_per_request_usd
- p95_per_request_usd

Quality (online — no ground truth required):
- citation_groundedness_avg
- nli_faithfulness_avg
```

### 3. Regression Gate Script (`scripts/compare_evals.py`)

**Compares:**
- Baseline metrics (main branch)
- Current metrics (PR branch)
- Threshold: 5% by default (configurable)

**Fails if:**
- Latency increases >5%
- Quality decreases >5%
- Cost increases >5%

### 4. Regression Gate in `.github/workflows/ci.yml` (extended `evals-golden` job)

**On every PR:**
1. Runs offline evaluations against `evals/datasets/golden_ci.jsonl`
2. Compares against committed `evals/reports/baseline.json`
3. Blocks PR if regressions detected
4. Comments with regression details

## Setup Instructions

### Step 1: Set Environment Variables

```bash
# For development with LangFuse
export LANGFUSE_PUBLIC_KEY=pk_...
export LANGFUSE_SECRET_KEY=sk_...

# For testing (disabled)
export DOC_PROFILE=demo  # Disables LangFuse
```

### Step 2: Install Dependencies

```bash
# langfuse is in requirements/base.txt
pip install -r requirements/base.txt  # Includes langfuse>=2.0.0
```

### Step 3: Configure Baseline (One-Time, commit to repo)

Already done! `evals/reports/baseline.json` is committed.

To regenerate from main branch:
```bash
git checkout main
PYTHONPATH=. python -m evals.run_evals \
  --dataset evals/datasets/golden_ci.jsonl \
  --judge-provider anthropic \
  --judge-model claude-haiku-4-5 \
  --output evals/reports/baseline.json
git add evals/reports/baseline.json
git commit -m "chore: update Phase 5 eval baseline"
```

### Step 4: Query and Monitor

```bash
# Start API with LangFuse enabled
export LANGFUSE_PUBLIC_KEY=pk_... LANGFUSE_SECRET_KEY=sk_...
PYTHONPATH=. uvicorn src.api.main:app --reload

# In another terminal, query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is RAG?"}'

# View dashboard
curl http://localhost:8000/observability/dashboard | jq .

# Output:
# {
#   "summary": { "total_requests": 1, ... },
#   "latency": {
#     "total_p50_ms": 1247.3,
#     "total_p95_ms": 1247.3,
#     "breakdown_pct": {
#       "retrieval": 18.2,
#       "reranking": 12.1,
#       "generation": 68.4,
#       "citation": 1.3
#     }
#   },
#   "cost": { "avg_per_request_usd": 0.00245 },
#   "quality": {
#     "citation_groundedness_avg": 0.92,
#     "nli_faithfulness_avg": 0.88
#   }
# }
```

## Testing

### Unit Tests

```bash
# Observability tests
pytest tests/unit/test_observability.py -v

# Metrics tests
pytest tests/unit/test_metrics.py -v

# Regression gate tests
pytest tests/unit/test_regression_gate.py -v
```

### Integration Test

```bash
# Full E2E with tracing enabled
LANGFUSE_PUBLIC_KEY=pk_... LANGFUSE_SECRET_KEY=sk_... \
PYTHONPATH=. python -c "
from src.api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)
response = client.post('/query', json={'query': 'What is RAG?'})
print(response.json())
# Should include request_id and all metrics
"
```

## Metrics Interpretation

### Latency Breakdown Example
```
Total P50: 1247.3 ms

Breakdown:
- Retrieval:   227 ms (18.2%)  ← BM25 + Vector Search
- Reranking:   151 ms (12.1%)  ← Cross-Encoder Rerank
- Generation:  855 ms (68.4%)  ← LLM inference
- Citation:     14 ms ( 1.3%)  ← Citation Verification

Interpretation:
Generation is the bottleneck (68.4% of total).
Could optimize by:
1. Using a faster model
2. Using streaming
3. Reducing context size
```

### Quality Metrics Example
```
Citation Groundedness: 0.92 (92% of citations verified)
NLI Faithfulness:      0.88 (88% of answer supported by chunks)

Interpretation:
- Citation coverage is strong (92%)
- Faithfulness could improve (88%)
- Consider reranking strategy improvements
```

### Cost Estimation Example
```
Cost per Request: $0.00245 (avg)
Cost at P95:      $0.00312

Annual projection (10K requests/day):
365 * 10K * $0.00245 = $8,927.50

Cost Optimization:
- Switch to cheaper model?
- Use batch inference?
- Cache common queries?
```

## Deployment Notes

### Docker

```dockerfile
# In docker/Dockerfile, ensure observability deps are included
# langfuse is in requirements/base.txt
RUN pip install -r requirements/base.txt

# docker-compose sets env vars
environment:
  - LANGFUSE_PUBLIC_KEY=${LANGFUSE_PUBLIC_KEY}
  - LANGFUSE_SECRET_KEY=${LANGFUSE_SECRET_KEY}
```

### Streamlit (Demo Mode)

```python
# In demo mode, observability is disabled
if os.getenv("DOC_PROFILE") == "demo":
    observer = RAGObserver(enabled=False)  # No-op
```

## Troubleshooting

### LangFuse traces not appearing

```
1. Check credentials: LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY set?
2. Check network: Can you reach https://cloud.langfuse.com?
3. Check logs: Do you see "LangFuse observability enabled"?
4. Verify flush: observer.flush_async() called after each request?
```

### Dashboard metrics all zeros

```
1. Check MetricsCollector is receiving data:
   python -c "from src.monitoring.metrics import get_metrics_collector; print(len(get_metrics_collector().metrics))"
2. Have you sent enough requests? (P95 needs at least 20 samples)
3. Is metrics_collector.record_request() being called in /query endpoint?
```

### Regression gate always failing

```
1. Baseline exists? evals/reports/baseline.json present? (committed to repo)
   If not: already committed as part of Phase 5
2. Threshold too strict? Default is 5%, try --threshold 10
3. Eval dataset: correct file is evals/datasets/golden_ci.jsonl
4. Check eval logs for errors: see artifact evals/reports/pr-current.json
```

## Files Changed/Created

### Week 1: Instrumentation
- ✅ `src/core/observability.py` (NEW)
- ✅ `tests/unit/test_observability.py` (NEW)
- ✅ `src/core/rag_orchestrator.py` (MODIFIED - added tracing)
- ✅ `src/api/main.py` (MODIFIED - minimal changes)
- ✅ `requirements/base.txt` (MODIFIED - added langfuse)

### Week 2: Metrics Dashboard
- ✅ `src/monitoring/metrics.py` (NEW)
- ✅ `tests/unit/test_metrics.py` (NEW)
- ✅ `src/api/main.py` (MODIFIED - added metrics recording and dashboard endpoint)
- ✅ `src/utils/log.py` (MODIFIED - replaced MetricsCollector)

### Week 3: Regression Gating
- ✅ `scripts/compare_evals.py` (NEW)
- ✅ `tests/unit/test_regression_gate.py` (NEW)
- ✅ `.github/workflows/ci.yml` (MODIFIED - extended evals-golden job)
- ✅ `evals/reports/baseline.json` (NEW - committed baseline)

## Next Steps (Post-Phase 5)

- [ ] Grafana dashboard integration for long-term trends
- [ ] Alert thresholds (PagerDuty for latency spikes)
- [ ] Cost attribution per LLM provider
- [ ] A/B testing framework (compare models, prompts)
- [ ] User feedback loop (thumbs up/down on answers)
- [ ] Fine-tuning based on eval failures

## Interview Stories

### "How do you ensure production RAG reliability?"

> At Marriott, we deployed an agent handling 10K+ guest queries daily. Without observability, we'd have no idea if accuracy was degrading. I instrumented the pipeline with LangFuse tracing to see every step: retrieval latency, reranking precision, generation tokens, citation accuracy. Now I have a dashboard showing P50/P95 latency breakdown, cost per request, and quality metrics. And I wired up regression gating so no code change ships unless it passes a golden dataset evaluation. This is how you build trust in production AI systems.

### "How would you scale an AI platform?"

> Observability is first-class, not an afterthought. The moment you deploy, you need distributed tracing to answer: Where's the bottleneck? Is generation or retrieval slowing us down? What's the cost per request? How are quality metrics trending? I built this with LangFuse + a metrics collector, so we can see the full stack at P50/P95. Then I added regression gating in CI/CD to prevent accuracy regressions from ever shipping.

### "Describe your observability architecture"

> Every RAG pipeline step is traced to LangFuse: retrieval, reranking, generation, citation verification. We compute P50/P95/P99 latencies per step and expose them on a dashboard. We also track cost per request and quality metrics (citation groundedness, NLI faithfulness). In CI/CD, we compare PR eval results against a baseline — if latency increases >5% or quality decreases >5%, the PR is blocked with a detailed comment. This gives us real-time visibility and prevents regressions.

## Approval Checklist

- [x] Week 1: LangFuse integration with correct span hierarchy (one trace/request, spans as children)
- [x] Week 1: Instrumentation in `RAGOrchestrator.run()`, not `main.py`
- [x] Week 1: `flush_async()` used everywhere (no synchronous flush in request path)
- [x] Week 2: `MetricsCollector` in `src/monitoring/metrics.py` (new one, old one updated for compatibility)
- [x] Week 2: `RequestMetrics` has no `mrr`/`ndcg` fields
- [x] Week 3: Regression comparison added to existing `evals-golden` job in `ci.yml`
- [x] Week 3: `evals/reports/baseline.json` committed to repo
- [x] Tests: All unit tests passing
- [x] Integration: E2E query with tracing + metrics recording
- [x] Interview ready: Stories prepared

## Timeline Summary

| Week | Deliverable | Status |
|------|-------------|--------|
| 1 | LangFuse tracing | ✅ Complete |
| 2 | Metrics + dashboard | ✅ Complete |
| 3 | Regression gating + docs | ✅ Complete |

**Total effort:** ~40-50 hours over 3 weeks

---

**Generated:** 2026-05-01  
**Last Updated:** 2026-05-01
