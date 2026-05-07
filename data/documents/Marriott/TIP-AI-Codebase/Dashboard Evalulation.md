
Here's a comprehensive review of the `emergingtech-tipai-ecmp-dashboard` project and how evaluation is performed.

---

## Libraries Used

The project uses no third-party evaluation frameworks (no deepeval, ragas, promptfoo, langsmith, braintrust, or openai-evals). The entire evaluation pipeline is custom-built from scratch using only these core dependencies:

|Library|Role in Evaluation|
|---|---|
|`httpx`|HTTP client for calling LLM APIs (generation + judge)|
|`asyncpg`|Async PostgreSQL driver for persisting test cases, runs, results|
|`pydantic`|Request/response model validation|
|`fastapi`|API framework hosting the evaluation endpoints|

---

## How Evaluation Works

The evaluation system is fully embedded in the dashboard — there's no separate eval service. It's orchestrated by three key files:

### Key Files

|File|Purpose|
|---|---|
|`src/adapters/inbound/routers/eval_runner.py`|Core engine — `POST /api/eval/run/start` triggers `_run_eval()` as an async background task|
|`src/adapters/inbound/routers/eval_runs.py`|CRUD for runs/results + run-to-run comparison|
|`src/adapters/inbound/routers/eval_testcases.py`|CRUD for ground-truth test cases|
|`src/adapters/outbound/llm_client.py`|Shared LLM client with retry + exponential backoff|
|`src/adapters/outbound/prompt_builder.py`|Builds system prompts for generation calls|

### Evaluation Pipeline (per test case)

The engine in `_run_eval()` follows this multi-stage pipeline for each test case:

Step 1 — LLM Generation Call Builds a system prompt (property data, taxonomy, coverage context) and calls the configured LLM (via LiteLLM or Ollama) to produce a structured JSON response: `answerability`, `confidence`, `draft_response`, `reasoning`, `bucket_seems_correct`, etc.

Step 2 — Deterministic Scoring (5 metrics)

|Metric|Logic|
|---|---|
|`ansMatch`|1.0 if LLM answerability == expected, else 0.0|
|`bucketMatch`|1.0 / 0.5 / 0.0 based on bucket correctness|
|`ambiguityMatch`|1.0 if ambiguity assessment matches expected|
|`coverage`|% of mapping fields present in property data|
|`latency`|1.0 if elapsed <= threshold (default 30s), else 0.0|

Step 3 — LLM-as-Judge Call A separate LLM call (model/backend are independently configurable) evaluates the generated response against a judge prompt with five criteria:

1. Faithfulness — every claim must be grounded in property data
2. Hallucination — no invented specifics
3. Response Quality — warm, specific, appropriate tone
4. Handoff Correctness — correct handoff decision given route/rag_mode
5. NONE Correctness — when no response was generated, was that right?

The judge outputs a score on a 1–5 scale (5 = send as-is, 4 = minor edit, 3 = needs work, 2 = major rewrite, 1 = discard) plus boolean flags (`faithfulness_ok`, `hallucination_ok`, `handoff_correct`).

Step 4 — Three-Tier Pass/Fail

Classification Pass = ansMatch ≥ 1.0 AND bucketMatch ≥ 0.5 AND ambiguityMatch ≥ 1.0

Response Pass = Classification Pass AND judge_score ≥ 4

Overall (Readiness) = Response Pass AND coverage ≥ 0.6 AND latency pass

Step 5 — Run Summary Aggregates pass rates across all test cases and persists to the `eval_runs` table.

### Data Model (3 PostgreSQL tables)

- `eval_test_cases` — ground truth (property, intent, message, expected answerability/bucket, tags, golden response)
- `eval_runs` — run metadata (model, backend, prompt version, config snapshot, status, summary)
- `eval_results` — per-case results (assessment JSON, scores JSON, token usage, elapsed time, pass/fail, judge details, trace data)

### Regression Comparison

`POST /api/eval/compare` joins two runs by `test_case_id` and classifies each case as regression (pass → fail), improvement (fail → pass), or unchanged.