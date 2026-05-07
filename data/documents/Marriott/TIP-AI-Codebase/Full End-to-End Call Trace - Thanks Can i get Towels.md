
---

## Full End-to-End Call Trace: "Thanks! Can I get towels?"

> Trace for a **compound prompt** containing an acknowledgment ("Thanks!") and a new request ("Can I get towels?") arriving at the `/v1/sessions/{session_id}/messages` endpoint.

### Phase 0: API Entry Point

**File:** `app/api/routers/sessions/messaging.py`

```
POST /v1/sessions/{session_id}/messages
  body: { "prompt": "Thanks! Can I get towels?" }
```

1. `send_message_v1()` is invoked by FastAPI.
2. Validates `X-Correlation-Id` header (if present).
3. Checks for **duplicate prompt** via in-memory LRU cache (`check_duplicate_prompt`).
4. Gets the Temporal workflow handle: `temporal_client.get_workflow_handle(session_id)`.
5. Generates `message_id` (e.g., `msg-a3f9c1d2`).
6. Records the prompt in the dedup cache.
7. Queries the workflow for **event mode** (`await handle.query("get_event_mode")`).
8. **Routes based on event mode:**
   - **`rest-sync` mode** → calls `send_message_blocking()` which does `handle.execute_update("send_message_and_wait", ...)` — blocks until response.
   - **`sse` mode** → sends `handle.signal("new_prompt", {...})` — returns 202 immediately.

### Phase 1: Temporal Workflow Receives the Prompt

**File:** `app/workflows/orchestrator_workflow.py`

#### SSE Mode Path (`new_prompt` signal, line 317):

1. Signal handler `new_prompt()` extracts prompt, shadow_mode, message_id, ui_context, correlation_id.
2. Stores `_current_message_prompt` and sets message context on event buffer.
3. Clears previous batch results (`__final_summary`, `current_message_nodes`).
4. Calls `session.add_new_prompt(prompt)` — adds to `pending_new_prompts` queue.
5. Increments **turn counter** and adds user message to conversation history.
6. Emits `USER_UTTERANCE_RECEIVED` event.

#### REST-Sync Mode Path (`send_message_and_wait` update, line 616):

1. Update handler `send_message_and_wait()` does the same setup as above.
2. **Blocks** waiting for prompt processing: `workflow.wait_condition(lambda: not self.session.has_pending_prompts())`.
3. **Blocks** waiting for aggregator summary: `workflow.wait_condition(lambda: self.session.get_node_result("__final_summary") is not None)`.
4. Calls `_get_response_for_completion()` to extract and return the response dict.

### Phase 2: Session Loop Picks Up the Prompt

**File:** `app/workflows/orchestrator_workflow.py` → `_run_session_loop()` (line 1769)

The main loop runs continuously while the session is active:

```
while session.is_session_active():
    1. _process_pending_prompts()   ← processes our prompt
    2. _execute_node_batch()        ← runs child workflows
    3. _handle_session_cycle_completion() ← generates summary
    4. Wait for next event (new_prompt / user_input / end_session)
```

### Phase 3: Process Pending Prompts

**File:** `app/workflows/orchestrator_workflow.py` → `_process_pending_prompts()` (line 983)

1. Pops `{"prompt": "Thanks! Can I get towels?", "shadow_mode": false}` from `pending_new_prompts`.
2. Calls `_prepare_prompt_for_processing()`:
   - Clears previous slot evaluation result.
   - Updates `session.user_prompt` to the new prompt.
   - Increments slot attempt counters.
3. **Slot filling check** — `_try_handle_slot_filling(prompt)` (line 1440):
   - Checks if there are incomplete nodes needing slot values.
   - If yes: uses LLM to evaluate whether the prompt fills slots, cancels nodes, or contains new requests.
   - If handled → `continue` (skip intent mapping).
   - If not handled → proceeds to step 4.
4. Calls `_process_prompt_as_new_intent(prompt, shadow_mode)`.

### Phase 4: Acknowledgment Detection + Intent Classification

**File:** `app/workflows/orchestrator_workflow.py` → `_process_prompt_as_new_intent()` (line 1054)

#### Step 4a: Acknowledgment Detection (line 1062)

Calls `_detect_and_route_acknowledgment(prompt)` (line 1249):

1. Imports `is_pure_acknowledgment()` from `app/workflows/acknowledgment_detector.py`.
2. **For "Thanks! Can I get towels?"** — the `is_pure_acknowledgment()` function checks:
   - Contains `?` → returns `False` immediately (question mark = not a pure ack).
   - Also: "can" is in `REQUEST_SIGNALS` → would return `False`.
3. **Result: NOT a pure acknowledgment** → returns without setting router mode.
4. Normal intent mapping proceeds.

> **Note:** If the prompt were just "Thanks!" (no question), it WOULD be detected as a pure acknowledgment. The system would set `router_mode_intent_id` to the configured acknowledgment intent, skip intent mapping entirely, and route directly to the ack worker — saving ~1-2 LLM calls.

#### Step 4b: Check Router Mode (line 1065)

Since acknowledgment detection didn't set `router_mode_intent_id`, this check is skipped.

#### Step 4c: Intent Mapping via LLM (line 1080)

Calls `_map_prompt_to_graph(prompt, conversation_history)` (line 2556):

1. Enhances context with slot filling context (if any).
2. Emits `INTENT_MAPPING_REQUESTED` event.
3. Calls **`IntentMapper.map_prompt_to_graph()`** (the Temporal activity wrapper).

This triggers the **Temporal activity** `agent_mapPromptToGraph`:

```
IntentMapper.map_prompt_to_graph()  [workflow component]
  └─> workflow.execute_activity("agent_mapPromptToGraph")  [Temporal activity]
        └─> PromptMapper(IntentSearchService(), GraphProcessor()).map_prompt_to_graph()
```

**Inside `PromptMapper.map_prompt_to_graph()`:**

| Step | Action | Detail |
|------|--------|--------|
| 1 | **Decompose** | LLM breaks "Thanks! Can I get towels?" into sub-queries, e.g. `["Can I get towels?"]` (the "thanks" part may be dropped as noise, or kept as a separate sub-query) |
| 2a | **Bypass mode (default)** | `bypass_intent_similarity=True` → fetches ALL active intents via `IntentSearchService.get_active_intents()` → `IntentRegistryClient.get_active_intents()` (SQL: `SELECT ... FROM intents WHERE status = 'active'`) |
| 2b | **Similarity mode (if bypass=False)** | Would run 3 parallel searches per sub-query: keywords, utterance patterns, embedding similarity |
| 3 | **LLM Mapping** | Passes sub-queries + candidate intents to LLM → generates a DAG with `{intent_id, params, dependencies}` for each sub-query |
| 4 | **Graph Processing** | `GraphProcessor.merge_nodes_by_intent()` deduplicates, `build_intent_graph()` validates → returns `IntentGraph` |

**Back in `_process_prompt_as_new_intent()`:**

5. Checks for interrupt (discard if user sent a new message).
6. Calls `_add_nodes_from_intent_graph(intent_graph, prompt)` — adds `IntentNode` objects to the session.
7. Emits `INTENT_MAPPING_COMPLETED` event with node details.

### Phase 5: Execute Node Batch (Child Workflows)

**File:** `app/workflows/orchestrator_workflow.py` → `_execute_node_batch()` (line 2019)

For each node in the intent graph (e.g., a "towels" intent node):

1. **`NodeScheduler`** determines which nodes are ready (dependencies satisfied).
2. **`_start_ready_nodes()`** iterates ready nodes:
   - Calls `ChildWorkflowManager.build_combined_input()`:
     - Fetches full intent definition from DB via `get_intent_by_id` activity.
     - Builds `CombinedInput` with sub-query, conversation context, filtered messages.
   - Calls `ChildWorkflowManager.start_child_workflow()`:
     - Builds a **`JobRequest`** with agent name, task, inputs, principal context.
     - Creates a **Nexus client**: `workflow.create_nexus_client(endpoint=service_name, service="IntentRuntimeService")`.
     - Executes `nexus_client.execute_operation("StartJob", job_request)`.
     - Emits `NEXUS_CALL_STARTED` event.
3. **Remote executor worker** (in a separate service) receives the `JobRequest`:
   - Runs the intent's tool chain (e.g., room service API to request towels).
   - Returns a `JobSnapshot` with status, messages, and tool results.
4. **`_await_child_completions()`** waits for all in-flight nodes:
   - Converts `JobSnapshot` → orchestrator result format via `convert_job_snapshot_to_orchestrator_result()`.
   - Stores result in `session.node_results[node_id]`.
   - Calls `aggregate_child_messages()` to add executor messages to conversation history.
   - Emits `NODE_COMPLETED` and `NEXUS_CALL_COMPLETED` events.

### Phase 6: Summary Generation (Aggregator)

**File:** `app/workflows/orchestrator_workflow.py` → `_handle_session_cycle_completion()` (line 2043) → `_produce_final_summary()` (line 2855)

After all nodes complete:

1. Checks: all nodes complete? No pending prompts? No interrupt?
2. **`_produce_final_summary()`**:
   - Collects unmatched queries and unknown intents (if any).
   - **LLM Aggregation mode** (`llm_aggregation=True`, default):
     - `SummaryGenerator.collect_result_parts()` — assembles user query, worker results per sub-query, unmatched queries, conversation history.
     - `SummaryGenerator.generate_final_summary()` — calls `agent_conversationAggregator` Temporal activity:
       - LLM synthesizes a coherent natural-language response from all worker results.
       - Returns `{"response": "You're welcome! I've requested towels for your room..."}`.
   - **Concatenation mode** (`llm_aggregation=False`):
     - `SummaryGenerator.generate_concatenated_summary()` — directly concatenates worker responses (no LLM call).
3. Stores result as `session.node_results["__final_summary"]`.
4. Adds aggregator response to conversation history (role=`agent`, source=`orchestrator`).
5. Emits `RESPONSE_AGGREGATED` event.

### Phase 7: Response Delivery to Client

Depends on event mode:

#### REST-Sync Mode

Back in `send_message_and_wait()`:
1. `workflow.wait_condition(lambda: __final_summary is not None)` unblocks.
2. `_get_response_for_completion()` builds the response dict:
   - `response` — aggregator's natural language text.
   - `intent_mapping` — which intents were matched, with IDs and labels.
   - `node_results` — per-node messages and tool results.
3. Returns dict to `send_message_blocking()` in the API layer.
4. API enriches `intent_details` with labels from `IntentRegistryClient.get_intent_by_id()`.
5. Returns `V1MessageResponse` with status 202.

#### SSE Mode

1. Events were emitted throughout processing via `WorkflowEventBuffer`.
2. The `RESPONSE_AGGREGATED` event carries the final response text.
3. Client receives all events through the SSE stream (`/v1/sessions/{session_id}/events`).

---

## Complete Visual Flow Diagram

```
CLIENT
  │
  ▼
POST /v1/sessions/{session_id}/messages
  {"prompt": "Thanks! Can I get towels?"}
  │
  ▼
┌─────────────────────────────────────────────────┐
│  messaging.py: send_message_v1()                │
│  ├─ Validate & dedup                            │
│  ├─ Get workflow handle                         │
│  ├─ Query event_mode                            │
│  └─ Route: signal("new_prompt") or              │
│           update("send_message_and_wait")        │
└─────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────┐
│  OrchestratorWorkflow: new_prompt / send_message │
│  ├─ Queue prompt in session.pending_new_prompts  │
│  ├─ Increment turn counter                       │
│  └─ Add to conversation history                  │
└─────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────┐
│  _run_session_loop()                            │
│  └─> _process_pending_prompts()                 │
│        │                                         │
│        ├─ _try_handle_slot_filling() → False     │
│        │  (no incomplete nodes needing slots)     │
│        │                                         │
│        └─ _process_prompt_as_new_intent()        │
│             │                                    │
│             ├─ _detect_and_route_acknowledgment() │
│             │    └─ is_pure_acknowledgment()      │
│             │       "Thanks! Can I get towels?"   │
│             │       → False (has "?" and "can")   │
│             │                                    │
│             ├─ Router mode check → skipped       │
│             │                                    │
│             └─ _map_prompt_to_graph()            │
│                  │                               │
│                  ▼                               │
│           ┌─────────────────────────────┐       │
│           │ IntentMapper (Temporal act.) │       │
│           │ └─> PromptMapper            │       │
│           │      ├─ LLM: Decompose      │       │
│           │      │  → ["get towels"]     │       │
│           │      ├─ IntentSearchService  │       │
│           │      │  └─ IntentRegistry DB │       │
│           │      │     (get_active_intents)│     │
│           │      └─ LLM: Map to DAG     │       │
│           │         → IntentGraph        │       │
│           └─────────────────────────────┘       │
│                  │                               │
│                  ▼                               │
│           _add_nodes_from_intent_graph()         │
└─────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────┐
│  _execute_node_batch()                          │
│  For each ready node:                            │
│    ├─ ChildWorkflowManager.build_combined_input()│
│    │   └─ get_intent_by_id() → full intent def  │
│    │                                             │
│    └─ ChildWorkflowManager.start_child_workflow()│
│        ├─ Build JobRequest                       │
│        ├─ Nexus client → StartJob                │
│        │   (remote executor worker)              │
│        ├─ Worker executes tools (e.g. room svc)  │
│        └─ Returns JobSnapshot → result stored    │
└─────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────┐
│  _handle_session_cycle_completion()              │
│  └─> _produce_final_summary()                   │
│       ├─ SummaryGenerator.collect_result_parts() │
│       │   (assembles user query + worker results)│
│       └─ SummaryGenerator.generate_final_summary()│
│           └─ agent_conversationAggregator        │
│              (LLM synthesizes final response)    │
│              → "You're welcome! I've requested   │
│                 towels for your room..."          │
│                                                  │
│  Result stored as __final_summary                │
└─────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────┐
│  RESPONSE DELIVERY                               │
│                                                  │
│  REST-Sync: send_message_and_wait() unblocks     │
│    └─> _get_response_for_completion()            │
│        └─> V1MessageResponse to client           │
│                                                  │
│  SSE: Events streamed throughout                 │
│    └─> RESPONSE_AGGREGATED event with text       │
└─────────────────────────────────────────────────┘
```

---

## Key Files Reference

| Layer | File | Class/Function |
|-------|------|---------------|
| API | `app/api/routers/sessions/messaging.py` | `send_message_v1()`, `send_message_blocking()` |
| Workflow | `app/workflows/orchestrator_workflow.py` | `OrchestratorWorkflow` |
| Ack Detection | `app/workflows/acknowledgment_detector.py` | `is_pure_acknowledgment()` |
| Intent Mapping (component) | `app/workflows/orchestrator_components/intent_mapper.py` | `IntentMapper` |
| Intent Mapping (activity) | `app/activities/intent_mapping.py` | `agent_mapPromptToGraph()` |
| Prompt Mapper | `app/intent_mapping/prompt_mapper.py` | `PromptMapper` |
| Intent Search | `app/intent_mapping/intent_search_service.py` | `IntentSearchService` |
| Registry Client | `app/registry/client.py` | `IntentRegistryClient` |
| Node Scheduling | `app/workflows/orchestrator_components/node_scheduler.py` | `NodeScheduler` |
| Child Workflows | `app/workflows/orchestrator_components/child_workflow_manager.py` | `ChildWorkflowManager` |
| Slot Evaluation | `app/workflows/orchestrator_components/slot_evaluator.py` | `SlotEvaluator` |
| Summary | `app/workflows/orchestrator_components/summary_generator.py` | `SummaryGenerator` |
| DB Schema | `app/database/init/01-create-intent-registry-schema.sql` | `intents` table |

---

*Source: `emergingtech-tipai-orchestrator` codebase analysis — April 2026*
