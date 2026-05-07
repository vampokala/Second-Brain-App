
I now have the complete picture. Here is a comprehensive report.

---

## 1. DeepEval Test Result Output Format

### File Locations

DeepEval stores test results locally in a hidden `.deepeval` directory:

|File|Purpose|
|---|---|
|`.deepeval/.temp_test_run_data.json`|Scratch file written during a run, deleted when complete|
|`.deepeval/.latest_test_run.json`|Final saved results (persisted under key `testRunData`)|

You can also set `DEEPEVAL_RESULTS_FOLDER` env var to save timestamped result files to a custom directory.

### Top-Level JSON Structure (`.latest_test_run.json`)

{

"testRunData": {

"testFile": "test_ack_eval_offline.py",

"testCases": [ /* LLMApiTestCase objects */ ],

"conversationalTestCases": [ /* ConversationalApiTestCase objects */ ],

"metricsScores": [ /* MetricScores aggregates */ ],

"traceMetricsScores": { /* TraceMetricScores by span type */ },

"identifier": "my-run-label",

"hyperparameters": { /* user-defined */ },

"prompts": [ /* PromptData objects */ ],

"testPassed": 42,

"testFailed": 3,

"runDuration": 12.5,

"evaluationCost": 0.023,

"datasetAlias": "golden_ack_dataset",

"datasetId": "..."

}

}

---

## 2. DeepEval Schemas (from Source)

### `LLMApiTestCase` — Per-Test-Case Fields

From the DeepEval source (`deepeval/test_run/api.py`):

|Field (JSON alias)|Type|Description|
|---|---|---|
|`name`|`str`|Test case name|
|`input`|`str`|User input / query|
|`actualOutput`|`str?`|LLM-generated output|
|`expectedOutput`|`str?`|Gold-standard expected output|
|`context`|`list?`|Ground-truth context|
|`retrievalContext`|`list?`|Retrieved context (for RAG)|
|`toolsCalled`|`list?`|Tools the LLM called|
|`expectedTools`|`list?`|Expected tool calls|
|`tokenCost`|`float?`|Token cost for generation|
|`completionTime`|`float?`|LLM completion time|
|`tags`|`List[str]?`|Custom tags|
|`success`|`bool?`|Overall pass/fail|
|`metricsData`|`List[MetricData]?`|Per-metric results|
|`runDuration`|`float?`|Total test case duration|
|`evaluationCost`|`float?`|Cost of evaluating metrics|
|`order`|`int?`|Execution order|
|`additionalMetadata`|`Dict?`|Free-form metadata|
|`comments`|`str?`|Reviewer comments|
|`trace`|`TraceApi?`|Full trace with spans|

### `MetricData` — Per-Metric Fields

From `deepeval/tracing/api.py`, this is the core unit of evaluation per metric:

class MetricData(BaseModel):

name: str # e.g. "Answer Relevancy"

threshold: float # e.g. 0.5

success: bool # did it pass the threshold?

score: Optional[float] = None # 0.0 – 1.0

reason: Optional[str] = None # LLM-generated explanation

strictMode: Optional[bool] = False # binary scoring mode

evaluationModel: Optional[str] = None # e.g. "gpt-4o"

error: Optional[str] = None # error message if metric failed

evaluationCost: Optional[float] = None # $ cost for this metric

verboseLogs: Optional[str] = None # detailed eval logs

### `MetricScores` — Aggregate Per-Metric (across all test cases)

class MetricScores(BaseModel):

metric: str # metric name

scores: List[float] # all individual scores

passes: int # count of passing cases

fails: int # count of failing cases

errors: int # count of errored cases

### `TraceMetricScores` — By Span Type

class TraceMetricScores(BaseModel):

agent: Dict[str, Dict[str, MetricScores]]

tool: Dict[str, Dict[str, MetricScores]]

retriever: Dict[str, Dict[str, MetricScores]]

llm: Dict[str, Dict[str, MetricScores]]

base: Dict[str, Dict[str, MetricScores]]

---

## 3. Existing Eval Result Storage in Your Codebase

There is no DeepEval installation or `.deepeval` directory in the codebase. The only reference to DeepEval is in the plan file at `.cursor/plans/general_ack_eval_suite_2ac30f8f.plan.md` (which is pending, not yet implemented).

However, the ECMP Dashboard (`emergingtech-tipai-ecmp-dashboard`) has a mature, custom eval result storage system that predates DeepEval integration:

### Database Schema (`db/schema.ddl`)

`eval_runs` table:

remote_schema_setup.sqlLines 80-105

CREATE TABLE eval_runs (

run_id TEXT NOT NULL,

timestamp TIMESTAMPTZ NOT NULL,

model TEXT NOT NULL,

backend TEXT NOT NULL,

prompt_version TEXT,

config_snapshot JSONB DEFAULT '{}',

selected_tags TEXT[] DEFAULT '{}',

summary JSONB DEFAULT '{}',

status TEXT DEFAULT 'running',

total_cases INTEGER DEFAULT 0,

created_at TIMESTAMPTZ DEFAULT now()

);

`eval_results` table:

remote_schema_setup.sqlLines 80-91

CREATE TABLE eval_results (

id SERIAL PRIMARY KEY,

run_id TEXT NOT NULL REFERENCES eval_runs(run_id),

test_case_id TEXT NOT NULL REFERENCES eval_test_cases(id),

assessment JSONB DEFAULT '{}',

scores JSONB DEFAULT '{}',

token_usage JSONB DEFAULT '{}',

elapsed_sec REAL DEFAULT 0,

pass BOOLEAN DEFAULT FALSE,

details JSONB DEFAULT '{}',

created_at TIMESTAMPTZ DEFAULT now()

);

`eval_test_cases` table:

remote_schema_setup.sqlLines 107-122

CREATE TABLE eval_test_cases (

id TEXT NOT NULL,

case_id TEXT,

property TEXT NOT NULL,

intent TEXT NOT NULL,

message TEXT NOT NULL,

expected_answerability TEXT DEFAULT '',

expected_bucket TEXT DEFAULT '',

expected_ambiguous BOOLEAN DEFAULT false,

tags TEXT[] DEFAULT '{}',

golden_response TEXT DEFAULT '',

notes TEXT DEFAULT '',

created_at TIMESTAMPTZ DEFAULT now(),

updated_at TIMESTAMPTZ DEFAULT now(),

source_assessment_id INTEGER

);

### Pydantic Models (`dashboard.py`)

The Pydantic models for eval results are in `emergingtech-tipai-ecmp-dashboard/src/domain/models/dashboard.py`:

dashboard.pyLines 296-307

class EvalResultCreate(BaseModel):

model_config = ConfigDict(populate_by_name=True)

run_id: Optional[str] = None # Optional — provided via URL path

test_case_id: str = Field("", alias="testCaseId")

assessment: Dict[str, Any] = Field(default_factory=dict)

scores: Dict[str, Any] = Field(default_factory=dict)

token_usage: Dict[str, Any] = Field(default_factory=dict, alias="tokenUsage")

elapsed_sec: float = 0

passed: bool = Field(False, alias="pass")

details: Dict[str, Any] = Field(default_factory=dict)

### Reporting API Endpoints

The dashboard exposes a full REST API for eval management in three routers:

|Router|File|Endpoints|
|---|---|---|
|eval_runs|`src/adapters/inbound/routers/eval_runs.py`|CRUD for runs + results, `POST /api/eval/compare` for run comparison|
|eval_testcases|`src/adapters/inbound/routers/eval_testcases.py`|CRUD + bulk import for golden test cases|
|eval_runner|`src/adapters/inbound/routers/eval_runner.py`|`POST /api/eval/run/start`, `GET /status/{id}`, `POST /abort/{id}` — full eval engine|

### Scores Shape (from eval_runner.py)

The eval runner writes these specific score fields per result:

scores = {

"ansMatch": float, # 1.0 if answerability matches expected

"bucketMatch": float, # 1.0/0.5/0.0 for bucket correctness

"ambiguityMatch": float, # 1.0 if ambiguity flag correct

"coverage": float, # property data coverage ratio

"latency": float, # 1.0 if under threshold

"judge_score": int | None # 1-5 from LLM judge

}

And the run summary:

summary = {

"completedCases": int,

"totalCases": int,

"passRate": float, # overall pass %

"classificationPassRate": float, # classification-only pass %

"responsePassRate": float # response quality pass %

}

### Run Comparison Utility

The `POST /api/eval/compare` endpoint in `eval_runs.py` (lines 149-197) provides baseline-vs-comparison diffing, categorizing results into `regressions`, `improvements`, and `unchanged`.

---

## Summary

- DeepEval outputs results to `.deepeval/.latest_test_run.json` under the key `testRunData`. Each test case carries `metricsData` (a list of `MetricData` with `name`, `score`, `threshold`, `success`, `reason`, `evaluationCost`, `error`). Aggregate `metricsScores` are computed at the run level.
- No DeepEval files exist in the codebase yet — the ACK eval suite plan references DeepEval but is in `pending` status.
- The ECMP Dashboard already has a full eval pipeline: Postgres-backed `eval_runs` / `eval_results` / `eval_test_cases` tables, Pydantic models, REST API endpoints for CRUD, bulk import, run execution, and run comparison. This is the existing pattern any new DeepEval integration should bridge to.