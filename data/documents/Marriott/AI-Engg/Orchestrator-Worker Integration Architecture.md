# Orchestrator ↔ Worker Template Integration Architecture

## Connection Method: Temporal Nexus (not REST API)

The `emergingtech-tipai-orchestrator` and `tipai-worker-template` are **not** connected through a traditional REST/HTTP API. They communicate **entirely through Temporal Nexus**, which is Temporal's native cross-service RPC mechanism. There is no HTTP endpoint on the worker that the orchestrator calls.

---

## How It Works

### 1. Orchestrator Dispatches Work via Nexus

The orchestrator's `ChildWorkflowManager` creates a Nexus client and calls the `StartJob` operation on the worker:

```python
# emergingtech-tipai-orchestrator/app/workflows/orchestrator_components/child_workflow_manager.py
nexus_client = workflow.create_nexus_client(
    endpoint=nexus_endpoint, service=nexus_service
)
handle = await nexus_client.execute_operation(
    "StartJob",
    job_request,
    schedule_to_close_timeout=timedelta(minutes=5),
)
```

- Default Nexus endpoint: `"agent-executor-runtime"`
- Default Nexus service: `"IntentRuntimeService"`
- Each intent in the registry can override `executor_service_name` to route to a different worker

### 2. Worker Exposes a Nexus Service Contract

The worker template registers an `IntentRuntimeService` Nexus handler with six operations:

| Operation | Type | Purpose |
|---|---|---|
| `StartJob` | Workflow-run (long) | Starts `AgentExecutorWorkflow` for an intent |
| `GetSnapshot` | Sync (fast) | Returns current job state |
| `SendEvent` | Sync (fast) | Sends PROVIDE_INPUT / CONFIRM / CANCEL signals |
| `AwaitUpdate` | Workflow-run (long) | Long-polls for state changes |
| `ListAgents` | Sync (fast) | Lists all registered intent names |
| `DescribeAgent` | Sync (fast) | Returns intent schema |

### 3. Worker Runs 3 Separate Temporal Workers Internally

The worker template uses a **three-worker architecture**, each polling a different task queue:

| Worker | Task Queue Pattern | Role |
|---|---|---|
| Nexus Handler | `nexus-{team}-{service}-q-{env}` | Receives Nexus calls from orchestrator |
| Executor | `{team}-{service}-q-{env}` | Runs `AgentExecutorWorkflow` (ReAct loop) |
| Activities | `{team}-{service}-tools-q-{env}` | Executes tool activities (API calls, LLM, etc.) |

---

## Data Flow

```
User → Frontend → FastAPI (orchestrator) → Temporal OrchestratorWorkflow
                                                  ↓
                                        Nexus "StartJob" call
                                                  ↓
                                     Worker: Nexus Handler receives call
                                                  ↓
                                     Worker: Starts AgentExecutorWorkflow
                                                  ↓
                                     Worker: ReAct loop (LLM → tool → LLM → ...)
                                                  ↓
                                     Result returned via Nexus to orchestrator
                                                  ↓
                                     Orchestrator aggregates all results → User
```

---

## Events Flow Back via Redis (SSE)

While the request/response goes through Nexus, **real-time UI events** (step updates, tool results, progress) flow through a separate path: **Redis Streams**. The worker publishes events using the orchestrator's `parent_workflow_id` as the stream key, so events land on the correct SSE channel for the frontend.

---

## Key Nexus Contract (Shared Between Both)

Both sides define the same contract.

**Orchestrator side** (`emergingtech-tipai-orchestrator/app/models/nexus_service.py`):

```python
class IntentRuntimeService:
    """Nexus service contract for Intent Runtime Service operations.
    This is a service contract definition that matches the executor's
    IntentRuntimeServiceHandler. The actual implementation is in the executor.
    """
```

**Worker side** (`tipai-worker-template/app/integration/nexus/handler.py`):

```python
@nexus_service
class IntentRuntimeService:
    """Nexus contract: names + IO types must match implementation methods."""
    StartJob: Operation[JobRequest, JobSnapshot]
    GetSnapshot: Operation[str, JobSnapshot]
    SendEvent: Operation[dict, JobStatusLite]
    AwaitUpdate: Operation[dict, JobUpdate]
    ListAgents: Operation[None, list[str]]
    DescribeAgent: Operation[str, Dict[str, Any]]
```

---

## Per-Intent Routing

Each intent registered in the orchestrator's intent registry can specify its own `executor_service_name`. This allows different worker deployments (each based on `tipai-worker-template` but with different intents/tools) to handle different types of requests. The orchestrator dynamically routes to the correct worker based on the intent.

---

## Orchestrator Role (The Brain)

- Decomposes user prompts into an intent graph via LLM activities
- Maps intents to registered agents using embedding similarity (pgvector) + LLM
- Dispatches work to remote executor workers via Temporal Nexus
- Aggregates results from multiple workers back into a unified response
- Manages conversation state, slot-filling, summarization

### Orchestrator Key Services

| Service | Purpose |
|---|---|
| FastAPI API | Session management, intent CRUD, health checks |
| Temporal Worker | Runs `OrchestratorWorkflow` + `SummarizerWorkflow` |
| Redis | Real-time SSE event streaming + caching |
| PostgreSQL (pgvector) | Intent registry with vector search |
| Neo4j | Property knowledge graphs |
| OpenTelemetry/Jaeger | Distributed tracing |

---

## Worker Template Role (The Hands)

- Receives intent execution requests via Nexus
- Loads intent definitions from YAML files
- Runs an LLM-driven ReAct loop (`AgentExecutorWorkflow`)
- Dispatches tool calls as Temporal activities
- Publishes real-time events to Redis for the UI

### Worker Key External APIs Consumed

| API | Purpose |
|---|---|
| UXL GraphQL | Marriott property data (federated GraphQL) |
| v2 Properties REST | Hotel detail sections |
| Akana Typeahead | Hotel name search/suggestions |
| LLM Provider (LiteLLM) | OpenAI, Azure, Bedrock models |
| Neo4j | Knowledge graph for property search |
| Redis | SSE event streaming |
| S3 | Large event payload offloading |

---

## Summary

| Aspect | Detail |
|---|---|
| **Connection** | Temporal Nexus RPC (not REST API) |
| **Orchestrator** | Brain — intent decomposition, mapping, aggregation |
| **Worker** | Hands — tool execution, LLM reasoning loops per intent |
| **Real-time events** | Redis Streams (side-channel for SSE to frontend) |
| **Benefits** | Type-safe, cross-namespace calls with built-in retries, timeouts, and cancellation propagation |
