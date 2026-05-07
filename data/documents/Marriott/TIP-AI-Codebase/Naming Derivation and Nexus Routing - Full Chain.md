# Naming Derivation and Nexus Routing — Full Chain

> How `.env` variables, intent YAML `routing.base`, the intent registry, and Temporal Nexus endpoints are linked end-to-end.

---

## 1. The Four Seed Variables

Everything starts from four values defined in the worker's `.env` file (`deploy/.env` or root `.env`):

| Variable | Example (ECMP Worker) | Example (Central Platform) | Purpose |
|---|---|---|---|
| `TIPAI_APP` | `tipai` | `tipai` | Application token (rarely changes) |
| `TIPAI_TEAM` | `ecmpwork` | `centralwork` | Team/product identifier |
| `TIPAI_SERVICE` | `ecmpworker` | `testworker` | Service/worker identifier |
| `DEPLOY_ENV` | `local` | `local` | Environment: `local`, `dev`, `test`, `stg`, `perf`, `prod`, `platform` |

The orchestrator has its own `.env` with separate `TIPAI_TEAM` / `TIPAI_SERVICE` (e.g., `ecmporch` / `orchestrator`), which only affects the orchestrator's own namespace and queues.

---

## 2. Derived Names — The Naming Contract

`PlatformSettings.validate_namespace_format()` in `app/config/settings.py` derives **all** runtime names from the seed variables. No names are hard-coded.

### 2.1 Worker-side names (derived by the ECMP worker)

| Derived Name            | Formula                                             | ECMP Local Example                  |
| ----------------------- | --------------------------------------------------- | ----------------------------------- |
| **Temporal Namespace**  | `{TIPAI_APP}-{TIPAI_TEAM}-{DEPLOY_ENV}`             | `tipai-ecmpwork-local`              |
| **Nexus Endpoint Name** | `{TIPAI_TEAM}-{TIPAI_SERVICE}-{DEPLOY_ENV}`         | `ecmpwork-ecmpworker-local`         |
| **Executor Task Queue** | `{TIPAI_TEAM}-{TIPAI_SERVICE}-q-{DEPLOY_ENV}`       | `ecmpwork-ecmpworker-q-local`       |
| **Tools Task Queue**    | `{TIPAI_TEAM}-{TIPAI_SERVICE}-tools-q-{DEPLOY_ENV}` | `ecmpwork-ecmpworker-tools-q-local` |
| **Nexus Task Queue**    | `nexus-{executor_task_queue}`                       | `nexus-ecmpwork-ecmpworker-q-local` |

**Source code** (`app/config/settings.py`, lines 472–481):
```python
derived_namespace      = f"{app}-{team}-{deploy_env}"
derived_endpoint       = f"{team}-{service}-{deploy_env}"
derived_executor_queue = f"{team}-{service}-q-{deploy_env}"
derived_tools_queue    = f"{team}-{service}-tools-q-{deploy_env}"
```

The Nexus task queue is derived from the executor queue:
```python
@property
def nexus_service_task_queue(self) -> str:
    return f"nexus-{self.executor_task_queue}"
```

### 2.2 Orchestrator-side names (derived by the orchestrator)

| Derived Name | Formula | ECMP Orchestrator Local Example |
|---|---|---|
| **Orchestrator Namespace** | `{TIPAI_APP}-{TIPAI_TEAM}-{DEPLOY_ENV}` | `tipai-ecmporch-local` |

The orchestrator's namespace is where orchestrator workflows run. It is a *different* Temporal namespace from the worker namespace.

### 2.3 Validation patterns

All derived names are validated at startup by `app/config/namespace_validation.py`:

| Name | Regex Pattern |
|---|---|
| Nexus Endpoint | `^[a-z0-9]+-[a-z0-9-]+-{env}$` |
| Executor Queue | `^[a-z0-9]+-[a-z0-9-]+-q-{env}$` |
| Tools Queue | `^[a-z0-9]+-[a-z0-9-]+-tools-q-{env}$` |
| Namespace | `^[a-z0-9]+-[a-z0-9-]+-{env}$` |

---

## 3. Intent YAML `routing.base` — Override or Default

Each intent YAML file (`app/intents/*.yaml`) has an optional `routing` section:

```yaml
routing:
  base: ecmpwork-ecmpworker       # explicit override
  #executor_model: anthropic/claude-sonnet-4-20250514  # optional per-intent model
```

### Resolution order (in `register_intents.py`)

The registration script uses this priority to determine the "base" for `executor_service_name`:

1. **`routing.base`** from the intent YAML (highest priority, per-intent override)
2. **`routing.endpoint_base`** (legacy alias, same behavior)
3. **`{TIPAI_TEAM}-{TIPAI_SERVICE}`** from the environment (default fallback)

Then:
```
executor_service_name = "{base}-{DEPLOY_ENV}"
```

### Why `routing.base` exists

Most intents for a worker use the same endpoint. The default (`TIPAI_TEAM-TIPAI_SERVICE`) handles this automatically. But when a worker needs to register intents targeting a *different* Nexus endpoint (e.g., a shared worker registering intents for multiple teams), `routing.base` provides a per-intent override.

---

## 4. The Intent Registry — Storing the Link

Running `register_intents.py` sends a payload to the orchestrator's REST API (`POST /intent/upsert`). The payload includes:

```json
{
  "name": "policy/policyqa",
  "routing": {
    "executor_service_name": "ecmpwork-ecmpworker-local"
  }
}
```

The orchestrator stores this in its intent registry database. At runtime, when the orchestrator needs to route a user query to a worker, it reads `executor_service_name` from the registry to know *which Nexus endpoint to call*.

### Verify registered value

```bash
curl -s http://localhost:8000/intent/by-name/policy/policyqa/details | python3 -m json.tool
```

Look for:
```json
"routing": {
    "executor_service_name": "ecmpwork-ecmpworker-local"
}
```

---

## 5. Temporal Nexus Endpoint — The Router

A Nexus endpoint must be registered in Temporal server itself. It maps a logical endpoint name to a physical namespace + task queue:

| Field | Value |
|---|---|
| **Name** | `ecmpwork-ecmpworker-local` |
| **Target Namespace** | `tipai-ecmpwork-local` |
| **Target Task Queue** | `nexus-ecmpwork-ecmpworker-q-local` |

### Create via API (avoids CSRF issues with the UI)

```bash
curl -X POST http://localhost:7243/api/v1/nexus/endpoints \
  -H "Content-Type: application/json" \
  -d '{
    "spec": {
      "name": "ecmpwork-ecmpworker-local",
      "description": "ECMP worker Nexus endpoint (local)",
      "target": {
        "worker": {
          "namespace": "tipai-ecmpwork-local",
          "taskQueue": "nexus-ecmpwork-ecmpworker-q-local"
        }
      }
    }
  }'
```

### Verify

```bash
curl -s http://localhost:7243/api/v1/nexus/endpoints | python3 -m json.tool
```

---

## 6. The Full Request Flow — End to End

```
┌──────────┐     ┌──────────────────────┐     ┌────────────────┐     ┌────────────────┐
│  Client   │────>│   Orchestrator API   │────>│ Orchestrator   │────>│ Intent         │
│  (curl)   │     │   POST /messages     │     │ Workflow       │     │ Registry DB    │
└──────────┘     └──────────────────────┘     └───────┬────────┘     └────────┬───────┘
                                                       │                       │
                                    ┌──────────────────┘                       │
                                    │ Reads executor_service_name              │
                                    │ = "ecmpwork-ecmpworker-local"            │
                                    ▼                                          │
                           ┌─────────────────────┐                            │
                           │ Temporal Nexus       │                            │
                           │ Endpoint Lookup      │                            │
                           │ "ecmpwork-ecmpworker │                            │
                           │  -local"             │                            │
                           └────────┬─────────────┘                            │
                                    │ Routes to:                               │
                                    │  namespace: tipai-ecmpwork-local         │
                                    │  taskQueue: nexus-ecmpwork-ecmpworker-   │
                                    │             q-local                      │
                                    ▼                                          │
                           ┌──────────────────────┐                            │
                           │  Nexus Handler Worker │ (polls nexus-ecmpwork-    │
                           │  (handler.py)         │  ecmpworker-q-local)      │
                           └────────┬──────────────┘                           │
                                    │ Starts AgentExecutorWorkflow on          │
                                    │ ecmpwork-ecmpworker-q-local              │
                                    ▼                                          │
                           ┌──────────────────────┐                            │
                           │  Executor Worker      │ (polls ecmpwork-          │
                           │  (workflow.py)        │  ecmpworker-q-local)      │
                           └────────┬──────────────┘                           │
                                    │ Schedules activities on                  │
                                    │ ecmpwork-ecmpworker-tools-q-local        │
                                    ▼                                          │
                           ┌──────────────────────┐                            │
                           │  Activities Worker    │ (polls ecmpwork-          │
                           │  (activities.py)      │  ecmpworker-tools-q-local)│
                           └──────────────────────┘                            │
```

### Step-by-step

| Step | Component | Action | Key Value Used |
|---|---|---|---|
| 1 | Client | `POST /messages` with prompt | N/A |
| 2 | Orchestrator API | Starts `OrchestratorWorkflow` | Orchestrator namespace: `tipai-ecmporch-local` |
| 3 | Orchestrator Workflow | Maps prompt to intent via embedding search | Returns `policy/policyqa` |
| 4 | Orchestrator Workflow | Fetches intent from registry | Gets `executor_service_name: ecmpwork-ecmpworker-local` |
| 5 | `ChildWorkflowManager` | Creates Nexus client: `workflow.create_nexus_client(endpoint="ecmpwork-ecmpworker-local", service="IntentRuntimeService")` | Uses `executor_service_name` as endpoint |
| 6 | Temporal Server | Looks up Nexus endpoint `ecmpwork-ecmpworker-local` | Routes to `tipai-ecmpwork-local` / `nexus-ecmpwork-ecmpworker-q-local` |
| 7 | Nexus Handler Worker | Receives `StartJob` operation, resolves intent, starts `AgentExecutorWorkflow` | Intent name from `JobRequest.agent` |
| 8 | Executor Worker | Runs ReAct loop, schedules tool activities | Executor queue: `ecmpwork-ecmpworker-q-local` |
| 9 | Activities Worker | Executes tool activities | Tools queue: `ecmpwork-ecmpworker-tools-q-local` |
| 10 | Return | Result flows back through Nexus to orchestrator to API | N/A |

---

## 7. The Critical Matching Rule — Three Values Must Agree

These three values reference the same logical entity and **must be identical**:

| Source | Where it lives | How it's set |
|---|---|---|
| **Temporal Nexus Endpoint Name** | Temporal server (via UI or API) | `curl POST /api/v1/nexus/endpoints` |
| **Worker `nexus_endpoint_name`** | Worker runtime (`settings.py`) | Derived as `{TIPAI_TEAM}-{TIPAI_SERVICE}-{DEPLOY_ENV}` |
| **Registry `executor_service_name`** | Intent registry DB | Set by `register_intents.py` from `routing.base` or `TIPAI_TEAM-TIPAI_SERVICE` + `DEPLOY_ENV` |

If any of these **three** don't match, you get one of these errors:

| Mismatch | Error |
|---|---|
| Registry != Temporal endpoint | `BadScheduleNexusOperationAttributes: endpoint "xyz" not found` |
| Temporal endpoint task queue != Worker poll queue | Nexus operation timeout (no worker polling that queue) |
| Worker namespace != Temporal endpoint target namespace | Nexus operation timeout (wrong namespace) |

---

## 8. Common Scenarios

### Scenario A: Changed `.env` but didn't re-register intents

**Symptom**: `endpoint "old-name-local" not found`

**Root cause**: `.env` was updated (e.g., `TIPAI_TEAM` changed), but `register_intents.py` was not re-run. The intent registry still has the old `executor_service_name`.

**Fix**:
```bash
cd emergingtech-tipai-ecmp-worker
set -a && source deploy/.env && set +a
.venv/bin/python scripts/register_intents.py --deploy-env local
```

### Scenario B: Re-registered intents but didn't create Temporal endpoint

**Symptom**: `BadScheduleNexusOperationAttributes: endpoint "new-name-local" not found`

**Root cause**: Intent registry has the new name, but Temporal server doesn't have a matching Nexus endpoint.

**Fix**: Create the endpoint (see Section 5).

### Scenario C: Temporal endpoint exists but worker isn't polling the right queue

**Symptom**: Nexus operation timeout (the call hangs, then times out)

**Root cause**: The Nexus endpoint targets `nexus-ecmpwork-ecmpworker-q-local` but the worker is polling a different queue.

**Fix**: Ensure the worker's `.env` variables produce the same derived queue that the endpoint targets. Restart the worker.

### Scenario D: `routing.base` in YAML doesn't match the worker's `.env`

**Symptom**: Intent registers with one endpoint name, but the worker advertises a different one.

**Root cause**: `routing.base` in the intent YAML is different from `{TIPAI_TEAM}-{TIPAI_SERVICE}` in `.env`.

**Fix**: Align `routing.base` with the `.env` values, or create a separate Nexus endpoint for the override.

---

## 9. File Reference — Source of Truth for Each Piece

| File | Repository | What It Controls |
|---|---|---|
| `deploy/.env` (or root `.env`) | `emergingtech-tipai-ecmp-worker` | `TIPAI_TEAM`, `TIPAI_SERVICE`, `DEPLOY_ENV`, `TIPAI_APP` |
| `app/config/settings.py` | `emergingtech-tipai-ecmp-worker` | Derives namespace, endpoint, queues from `.env` |
| `app/config/namespace_validation.py` | `emergingtech-tipai-ecmp-worker` | Validates all derived name formats |
| `app/intents/*.yaml` | `emergingtech-tipai-ecmp-worker` | `routing.base` per-intent override |
| `scripts/register_intents.py` | `emergingtech-tipai-ecmp-worker` | Builds `executor_service_name` and sends to registry |
| `app/integration/nexus/handler.py` | `emergingtech-tipai-ecmp-worker` | Nexus handler polls `nexus_service_task_queue` |
| `app/entrypoints/worker.py` | `emergingtech-tipai-ecmp-worker` | Starts all three sub-workers with derived queues |
| `docker/.env` | `emergingtech-tipai-orchestrator` | Orchestrator's `TIPAI_TEAM`, `TIPAI_SERVICE` |
| `app/workflows/.../child_workflow_manager.py` | `emergingtech-tipai-orchestrator` | Reads `executor_service_name` from registry, creates Nexus client |
| `app/activities/intent_registry.py` | `emergingtech-tipai-orchestrator` | Fetches intent details including `executor_service_name` |
| `app/models/tool_definitions.py` | `emergingtech-tipai-orchestrator` | `AgentIntent.executor_service_name` field definition |

---

## 10. Quick Verification Checklist

Run these commands to verify everything is aligned:

```bash
# 1. Check what the worker derives from .env
cd emergingtech-tipai-ecmp-worker
set -a && source deploy/.env && set +a
echo "Namespace:     tipai-${TIPAI_TEAM}-${DEPLOY_ENV}"
echo "Endpoint:      ${TIPAI_TEAM}-${TIPAI_SERVICE}-${DEPLOY_ENV}"
echo "Executor Q:    ${TIPAI_TEAM}-${TIPAI_SERVICE}-q-${DEPLOY_ENV}"
echo "Tools Q:       ${TIPAI_TEAM}-${TIPAI_SERVICE}-tools-q-${DEPLOY_ENV}"
echo "Nexus Q:       nexus-${TIPAI_TEAM}-${TIPAI_SERVICE}-q-${DEPLOY_ENV}"

# 2. Check what's in the intent registry
curl -s http://localhost:8000/intent/by-name/policy/policyqa/details \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('Registry executor_service_name:', d['routing']['executor_service_name'])"

# 3. Check what Nexus endpoints exist in Temporal
curl -s http://localhost:7243/api/v1/nexus/endpoints \
  | python3 -c "
import sys, json
for ep in json.load(sys.stdin).get('endpoints', []):
    s = ep['spec']
    t = s['target']['worker']
    print(f\"  {s['name']}  ->  ns={t['namespace']}  q={t['taskQueue']}\")
"

# 4. Verify all three match
# The endpoint name from step 1, 2, and 3 must be identical.
```

---

## 11. Visual Summary — Derivation Map

```
deploy/.env
├── TIPAI_APP=tipai
├── TIPAI_TEAM=ecmpwork
├── TIPAI_SERVICE=ecmpworker
└── DEPLOY_ENV=local
         │
         ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                  settings.py (PlatformSettings)             │
    │                                                             │
    │  Namespace:      tipai-ecmpwork-local                       │
    │  Endpoint:       ecmpwork-ecmpworker-local          ◄──┐   │
    │  Executor Q:     ecmpwork-ecmpworker-q-local           │   │
    │  Tools Q:        ecmpwork-ecmpworker-tools-q-local     │   │
    │  Nexus Q:        nexus-ecmpwork-ecmpworker-q-local     │   │
    └─────────────────────────────────────────────────────────┼───┘
                                                              │
    ┌─────────────────────────────────────────────────────────┼───┐
    │  policyqa.yaml                                          │   │
    │                                                         │   │
    │  routing:                                               │   │
    │    base: ecmpwork-ecmpworker   ─── register_intents.py ─┘   │
    │                                    appends -{DEPLOY_ENV}    │
    │                                    = ecmpwork-ecmpworker-   │
    │                                      local                  │
    └─────────────────────────────────────────────┬───────────────┘
                                                  │
                                                  ▼
    ┌─────────────────────────────────────────────────────────────┐
    │  Intent Registry (Orchestrator DB)                          │
    │                                                             │
    │  policy/policyqa                                            │
    │    routing.executor_service_name = ecmpwork-ecmpworker-local│
    └─────────────────────────────────────────────┬───────────────┘
                                                  │
    ┌─────────────────────────────────────────────┼───────────────┐
    │  ChildWorkflowManager (Orchestrator)        │               │
    │                                             │               │
    │  executor_service_name ◄────────────────────┘               │
    │                                                             │
    │  nexus_client = workflow.create_nexus_client(               │
    │      endpoint="ecmpwork-ecmpworker-local",                  │
    │      service="IntentRuntimeService"                         │
    │  )                                                          │
    └─────────────────────────────────────────────┬───────────────┘
                                                  │
                                                  ▼
    ┌─────────────────────────────────────────────────────────────┐
    │  Temporal Nexus Endpoint                                    │
    │                                                             │
    │  Name:       ecmpwork-ecmpworker-local                      │
    │  Namespace:  tipai-ecmpwork-local                           │
    │  Task Queue: nexus-ecmpwork-ecmpworker-q-local              │
    └─────────────────────────────────────────────┬───────────────┘
                                                  │
                                                  ▼
    ┌─────────────────────────────────────────────────────────────┐
    │  Nexus Handler Worker (handler.py)                          │
    │                                                             │
    │  Polls: nexus-ecmpwork-ecmpworker-q-local                   │
    │  Starts: AgentExecutorWorkflow                              │
    │    on queue: ecmpwork-ecmpworker-q-local                    │
    └─────────────────────────────────────────────────────────────┘
```

---

*Last updated: 2026-04-09*
