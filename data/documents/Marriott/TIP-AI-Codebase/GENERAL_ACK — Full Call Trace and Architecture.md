# GENERAL_ACK — Full Call Trace and Architecture

> **Codebase:** ECMP-TIP-Review (Orchestrator + ECMP Worker)
> **Trace Message:** `"Thanks!"`
> **Date:** 2026-04-09
> **Status:** Living document — update as codebase evolves

---

## Table of Contents

- [[#1 — High-Level Flow Diagram]]
- [[#2 — Call Trace Step by Step]]
  - [[#Step 1 — API Entry (messaging.py)]]
  - [[#Step 2 — Temporal Signal Dispatch]]
  - [[#Step 3 — Orchestrator Signal Handler (new_prompt)]]
  - [[#Step 4 — Session Loop Picks Up the Prompt]]
  - [[#Step 5 — Acknowledgment Detection (the fork)]]
  - [[#Step 6 — Router Mode Creates the Worker Node]]
  - [[#Step 7 — Nexus Dispatch to ECMP Worker]]
  - [[#Step 8 — Worker Executes acknowledgment_handler_activity]]
  - [[#Step 9 — Response Aggregation and Delivery]]
- [[#3 — The Deterministic ACK Detector]]
- [[#4 — Event Emissions Along the Path]]
- [[#5 — File Reference Table]]
- [[#6 — Configuration Reference]]
- [[#7 — What Does NOT Happen on the ACK Path]]
- [[#8 — Known Issues and Gaps]]

---

## 1 — High-Level Flow Diagram

```
Client                    Orchestrator API             Temporal Workflow             ECMP Worker
  │                            │                            │                           │
  │  POST /v1/sessions/        │                            │                           │
  │  {id}/messages             │                            │                           │
  │  {"prompt":"Thanks!"}      │                            │                           │
  │ ─────────────────────────► │                            │                           │
  │                            │  signal("new_prompt",      │                           │
  │                            │    {prompt,message_id})     │                           │
  │                            │ ─────────────────────────► │                           │
  │  ◄──── 202 Accepted ───── │                            │                           │
  │   (SSE mode: immediate)    │                            │                           │
  │                            │                            │  _process_prompt_as_      │
  │                            │                            │    new_intent()            │
  │                            │                            │       │                    │
  │                            │                            │       ▼                    │
  │                            │                            │  _detect_and_route_        │
  │                            │                            │    acknowledgment()        │
  │                            │                            │       │                    │
  │                            │                            │       ▼                    │
  │                            │                            │  is_pure_acknowledgment()  │
  │                            │                            │  "Thanks!" ──► True        │
  │                            │                            │       │                    │
  │                            │                            │       ▼                    │
  │                            │                            │  Set router_mode_intent_id │
  │                            │                            │  = chat/mock_thank_you_    │
  │                            │                            │    greetings               │
  │                            │                            │       │                    │
  │                            │                            │       ▼                    │
  │                            │                            │  _process_router_mode()    │
  │                            │                            │  Create IntentNode         │
  │                            │                            │       │                    │
  │                            │                            │       ▼                    │
  │                            │                            │  Nexus dispatch ──────────►│
  │                            │                            │                            │ acknowledgment_
  │                            │                            │                            │ handler_activity()
  │                            │                            │                            │   │
  │                            │                            │                            │   ▼
  │                            │                            │                            │ is_closure_message()
  │                            │                            │                            │ → True ("thanks")
  │                            │                            │                            │   │
  │                            │                            │                            │   ▼
  │                            │                            │                            │ generate_
  │                            │                            │                            │ acknowledgment_
  │                            │                            │                            │ response() [LLM]
  │                            │                            │                            │   │
  │                            │                            │  ◄──────────────────────── │   ▼
  │                            │                            │  {response, closure=True}  │ "You're welcome!
  │                            │                            │       │                    │  Have a great day!"
  │                            │                            │       ▼                    │
  │                            │                            │  Aggregator builds         │
  │                            │                            │  __final_summary           │
  │                            │                            │       │                    │
  │  ◄───── SSE event ─────── │ ◄──── Redis stream ─────── │  emit AGENT_MESSAGE        │
  │  or REST-sync response     │                            │                            │
```

---

## 2 — Call Trace Step by Step

### Step 1 — API Entry (messaging.py)

**File:** `emergingtech-tipai-orchestrator/app/api/routers/sessions/messaging.py`
**Function:** `send_message_v1()` — line 129
**HTTP:** `POST /v1/sessions/{session_id}/messages`

The request body is deserialized into `V1MessageRequest` (defined in `app/models/api_requests.py`, line 250) with fields:

| Field | Type | Required | Purpose |
|---|---|---|---|
| `prompt` | `str` | Yes | The user's message text |
| `node_id` | `str` | No | For slot-filling responses |
| `shadow_mode` | `bool` | No | A/B testing mode |
| `application_info` | `dict` | No | Client metadata |
| `ui_context` | `UIContext` | No | UI state context |

**What happens at the API layer:**

1. Validates optional `X-Correlation-Id` header
2. Checks for duplicate prompts using an in-memory LRU cache (`check_duplicate_prompt`)
3. Gets Temporal workflow handle: `temporal_client.get_workflow_handle(session_id)`
4. Generates a message ID: `msg-{uuid4().hex[:12]}`
5. Queries workflow for its `event_mode` (`sse` or `rest-sync`)
6. Routes to the appropriate dispatch path

### Step 2 — Temporal Signal Dispatch

Two paths exist depending on the session's `event_mode`:

#### SSE Mode (default)

```python
# messaging.py, line 222-231
await handle.signal(
    "new_prompt",
    {
        "prompt": request.prompt,        # "Thanks!"
        "shadow_mode": request.shadow_mode,
        "message_id": message_id,        # "msg-3c0f99c5701d"
        "ui_context": ui_context_dict,
        "correlation_id": x_correlation_id,
    },
)
```

Returns immediately with `202 Accepted` and `V1MessageResponse(accepted=True, message_id=...)`.
The client receives events via SSE stream at `GET /v1/sessions/{id}/events`.

#### REST-sync Mode

```python
# messaging.py, line 202-204
return await send_message_blocking(handle, request, message_id, x_correlation_id)
```

Calls `handle.execute_update("send_message_and_wait", ...)` which **blocks** until the workflow produces a response.

### Step 3 — Orchestrator Signal Handler (new_prompt)

**File:** `emergingtech-tipai-orchestrator/app/workflows/orchestrator_workflow.py`
**Class:** `OrchestratorWorkflow(BaseWorkflow)` — line 63
**Function:** `new_prompt()` — line 317 (decorated `@workflow.signal`)

When the signal arrives, the handler:

1. **Extracts payload fields** — `prompt`, `shadow_mode`, `message_id`, `ui_context`, `correlation_id`
2. **Stores UI context** as a `ui_context` role message in conversation history (if present)
3. **Sets message context** on the event buffer for trace correlation (`event_buffer.set_message_context(message_id)`)
4. **Clears previous batch results** — removes `__final_summary` from node results so stale data doesn't leak
5. **Queues the prompt** — `self.session.add_new_prompt(prompt.strip(), shadow_mode=shadow_mode)`
6. **Increments turn counter** — `self.session.increment_turn_counter()`
7. **Adds user message to conversation history** — `self.add_message(role="user", content="Thanks!", ...)`
8. **Emits event** — `USER_UTTERANCE_RECEIVED` with `{message, message_id, turn_number}`

> **Key point:** The signal handler only *queues* the prompt. Actual processing happens in the session loop.

### Step 4 — Session Loop Picks Up the Prompt

**Function:** `_run_session_loop()` — line 1769

The main workflow loop runs continuously. On each iteration it checks:

```python
if self.session.has_pending_prompts():
    await self._process_pending_prompts()
```

**Function:** `_process_pending_prompts()` — line 983

Pops the prompt from the queue and calls:

```python
await self._process_prompt_as_new_intent(prompt, shadow_mode)
```

### Step 5 — Acknowledgment Detection (the fork)

**Function:** `_process_prompt_as_new_intent()` — line 1054

This is the critical decision point. The **very first thing** this function does is check for acknowledgments:

```python
# Line 1061-1062
await self._detect_and_route_acknowledgment(prompt)
```

**Function:** `_detect_and_route_acknowledgment()` — line 1249

```python
async def _detect_and_route_acknowledgment(self, prompt: str) -> None:
    from app.workflows.acknowledgment_detector import is_pure_acknowledgment

    # Step 1: Deterministic pattern check
    if not is_pure_acknowledgment(prompt):
        return  # Not an ACK → continue to normal LLM intent mapping

    # Step 2: Look up the acknowledgment intent from config
    acknowledgment_intent_name = _settings.intent_mapping.acknowledgment_intent_name
    # Default: "chat/mock_thank_you_greetings"

    intent_data = await self._get_intent_id_by_name(acknowledgment_intent_name)
    # Calls Temporal activity "get_intent_by_name" → returns {id, name, ...}

    # Step 3: If found, set router mode (bypasses ALL intent mapping)
    if intent_data:
        intent_id = intent_data.get("id")
        self.session.state.router_mode_intent_id = intent_id
        self._cached_router_mode_intent_data = intent_data
```

Back in `_process_prompt_as_new_intent()`, the next check is:

```python
# Line 1064-1072
if self.session.state.router_mode_intent_id:
    await self._process_router_mode(prompt, shadow_mode)
    return  # ← Exits. Normal intent mapping is NEVER reached.
```

#### How `is_pure_acknowledgment("Thanks!")` resolves to True

**File:** `emergingtech-tipai-orchestrator/app/workflows/acknowledgment_detector.py` — line 68

For `"Thanks!"`, the function walks through these checks in order:

| Step | Check | Input | Result |
|---|---|---|---|
| 1 | Empty/invalid guard | `"Thanks!"` | Pass (non-empty string) |
| 2 | Lowercase + strip | | `msg_lower = "thanks!"` |
| 3 | Strip punctuation | | `msg_clean = "thanks"` |
| 4 | Question mark check | `"?" in "Thanks!"` | `False` → continue |
| 5 | CJK regex match | `CJK_ACK_RE.match("Thanks!")` | No match → continue |
| 6 | Latin regex match | `LATIN_ACK_RE.match("Thanks!")` | No match → continue |
| 7 | Exact phrase match | `"thanks" in PURE_ACK_PHRASES` | No (phrases are multi-word) → continue |
| 8 | Polite noise match | `"thanks!" in POLITE_NOISE_SET` | **Yes** → **return True** |

If the message were `"thanks"` (no `!`), the polite noise check would miss, but then:

| Step | Check | Result |
|---|---|---|
| 9 | Request signal check | No request words → continue |
| 10 | Single word token check | `"thanks" in PURE_ACK_TOKENS` → **return True** |

Either way, `"Thanks!"` is detected deterministically in **<100μs** with zero LLM calls.

### Step 6 — Router Mode Creates the Worker Node

**Function:** `_process_router_mode()` — line 1123

1. **Uses cached intent data** from Step 5 (avoids a redundant `get_intent_by_id` activity call)
2. **Generates node ID** — pattern: `n{intent_id}_f{execution_count+1}`, e.g., `n5_f1`
3. **Creates an IntentNode:**

```python
routed_node = IntentNode(
    id="n5_f1",
    intent_id=5,  # chat/mock_thank_you_greetings
    intent_name="chat/mock_thank_you_greetings",
    params={
        "sub_query": "Thanks!",
        "original_prompt": "Thanks!",
    },
    dependencies=[],
    parallel=True,
    needs_user_input=False,
)
```

4. **Stores node in session state:**

```python
self.session.state.nodes_by_id[routed_node.id] = routed_node
self.session.state.node_prompts[routed_node.id] = "Thanks!"
```

The node is then picked up by the scheduler in the next session loop iteration via `_execute_node_batch()`.

### Step 7 — Nexus Dispatch to ECMP Worker

The scheduler dispatches the node to the ECMP Worker via **Temporal Nexus**. The Nexus endpoint is determined by the intent's routing config:

```yaml
# mock_thank_you_greetings.yaml → routing
routing:
  base: ecmpwork-ecmpworker
```

The orchestrator's child workflow manager creates a Nexus operation targeting `enterprise-chat-ecmp-worker-local` (in local dev). This starts the **AgentExecutorWorkflow** in the worker.

### Step 8 — Worker Executes acknowledgment_handler_activity

**File:** `emergingtech-tipai-ecmp-worker/app/intents/mock_thank_you_greetings.yaml`
**Policy:** `max_react_loops: 0` — direct execution, no planner loop

The executor loads the intent definition and immediately executes the single tool: `acknowledgment_handler_activity`.

**File:** `emergingtech-tipai-ecmp-worker/app/tools/acknowledgment_handler.py`
**Function:** `acknowledgment_handler_activity()` — line 156 (Temporal activity)

The activity processes `"Thanks!"` in three steps:

#### Step 8a — Follow-up Detection

```python
# Line 216
if detect_follow_up(question):  # "Thanks!" → False (no ?, no signal words)
    return {"unsupported_request": True, ...}
```

`detect_follow_up("Thanks!")` checks for `?` and `FOLLOW_UP_SIGNALS` words (`can`, `could`, `please`, `need`, etc.). `"Thanks!"` has neither → returns `False` → no follow-up.

#### Step 8b — Closure vs. Mid-Conversation Classification

```python
# Line 224
is_closure = is_closure_message(question)  # "Thanks!" → True
```

`is_closure_message("Thanks!")` scans `CLOSURE_KEYWORDS` for substring matches. `"thank"` is in the set and appears in `"thanks!"` → returns `True`.

| Classification | Keywords | Example |
|---|---|---|
| **Closure** | thank, thanks, thx, ty, appreciate, goodbye, bye, have a nice day, see you, take care | "Thanks!", "Goodbye!" |
| **Mid-conversation ack** | (anything not matching above) | "Ok", "Got it", "Noted" |

#### Step 8c — LLM Response Generation

```python
# Line 229
response = await generate_acknowledgment_response(
    question="Thanks!",
    is_closure=True,
    principal_ctx=principal_ctx,
)
```

Because `is_closure=True`, the LLM receives the **closure system prompt**:

> *"You are a friendly and professional assistant handling conversation closures. Respond warmly and naturally to thank you messages and goodbyes."*

With examples like:
- "Thanks for your help!" → "You're welcome! Have a great day!"
- "Perfect—that solved it. Thank you." → "Glad I could help!"

The LLM call uses `temperature=0.7` and `max_tokens=100`.

**Returns:**

```python
{
    "response": "You're welcome! Have a great day!",
    "closure_detected": True
}
```

**Fallback:** If the LLM call fails, hardcoded fallback responses are used:
- Closure: `"You're welcome! Have a great day!"`
- Mid-conversation: `"Great! Let me know if you need anything else."`

### Step 9 — Response Aggregation and Delivery

Back in the orchestrator, the child workflow completes and the result is stored in `node_results`.

1. **Aggregator** produces `__final_summary` combining the node result
2. **`_emit_agent_response()`** — adds the agent's message to conversation history and emits `AGENT_MESSAGE_EMITTED` event

#### SSE Delivery

Events flow through:
```
WorkflowEventBuffer → flush() → Temporal activity "publish_workflow_events"
→ EventPublisher → Redis stream (sse:session:{id}) → EventStreamReader
→ SSE endpoint GET /v1/sessions/{id}/events → Client
```

#### REST-sync Delivery

The `send_message_and_wait()` update handler unblocks when `__final_summary` appears. It calls `_get_response_for_completion()` which builds and returns the full `V1MessageResponse`.

---

## 3 — The Deterministic ACK Detector

**File:** `emergingtech-tipai-orchestrator/app/workflows/acknowledgment_detector.py`

### Token Sets

| Set | Count | Purpose | Examples |
|---|---|---|---|
| `PURE_ACK_PHRASES` | 21 | Exact multi-word phrase matches | "thank you", "got it", "sounds good", "good morning" |
| `PURE_ACK_TOKENS` | 30 | Single-word token matches | "thanks", "ok", "perfect", "great", "yes", "hi" |
| `PURE_ACK_FILLERS` | 16 | Allowed filler words in composites | "you", "so", "much", "very", "for", "help" |
| `POLITE_NOISE_SET` | 21 | Exact match (including punctuation) | "thanks!", "got it thanks!", "thank you!!" |
| `REQUEST_SIGNALS` | 16 | Blockers that prevent ACK classification | "can", "could", "please", "need", "what", "how" |

### Regex Patterns

| Pattern | Matches | Examples |
|---|---|---|
| `LATIN_ACK_RE` | Spanish, French, German, Portuguese | gracias, merci, danke, obrigado |
| `CJK_ACK_RE` | Chinese, Japanese, Korean | 谢谢, ありがとう, 감사합니다, わかりました |

### Decision Logic (in order)

```
is_pure_acknowledgment(message)
│
├─ Empty/None → False
├─ Normalize: lowercase, strip punctuation
├─ Contains "?" → False (question mark blocker)
├─ CJK regex match → True
├─ Latin regex match → True
├─ Exact phrase match (PURE_ACK_PHRASES) → True
├─ Polite noise match (POLITE_NOISE_SET) → True
├─ Tokenize into words
├─ Any word in REQUEST_SIGNALS → False
├─ Single word in PURE_ACK_TOKENS → True
├─ ≤6 words: all (PURE_ACK_TOKENS ∪ PURE_ACK_FILLERS) AND at least one token → True
└─ >6 words → False
```

### Performance

All checks are set lookups and regex matches. Typical latency: **1–100μs** per call.

---

## 4 — Event Emissions Along the Path

| Order | Event | Emitted By | Payload (key fields) |
|---|---|---|---|
| 1 | `USER_UTTERANCE_RECEIVED` | `new_prompt()` signal handler | `{message, message_id, turn_number}` |
| 2 | *(intent mapping events skipped)* | — | Router mode bypasses `_map_prompt_to_graph()` entirely |
| 3 | `NODE_SCHEDULED` | Scheduler / `_execute_node_batch()` | `{node_id, intent_id, intent_name}` |
| 4 | `NEXUS_CALL_STARTED` | Child workflow manager | `{node_id, endpoint}` |
| 5 | Worker-side events | ECMP Worker executor | `NODE_RECEIVED`, `NODE_TOOL_STARTED`, `NODE_COMPLETED` |
| 6 | `NEXUS_CALL_COMPLETED` | Child workflow manager | `{node_id, success, duration_ms}` |
| 7 | `AGENT_MESSAGE_EMITTED` | `_emit_agent_response()` | `{message, source_node}` |

**Events that are NOT emitted on the ACK path:**
- `INTENT_MAPPING_REQUESTED` — skipped (no LLM mapping)
- `QUERY_DECOMPOSED` — skipped (no decomposition)
- `INTENT_RETRIEVAL_COMPLETED` — skipped (no embedding search)
- `INTENT_MAPPING_COMPLETED` — skipped (router mode does not emit this)

> **Note:** The reference test doc mentions `intent_mapping_completed` with `method: PURE_ACK` in the logs, but the current codebase does **not** emit this event on the ACK path. The router mode bypasses intent mapping entirely, so no mapping event is produced. This is a documentation-vs-code gap.

---

## 5 — File Reference Table

### Orchestrator (emergingtech-tipai-orchestrator/)

| File | Role in ACK Flow |
|---|---|
| `app/api/routers/sessions/messaging.py` | API endpoint — receives POST, dispatches Temporal signal/update |
| `app/models/api_requests.py` | `V1MessageRequest` model (line 250) |
| `app/models/api_responses.py` | `V1MessageResponse` model |
| `app/workflows/orchestrator_workflow.py` | Main workflow: signal handler, session loop, ACK detection, router mode |
| `app/workflows/acknowledgment_detector.py` | `is_pure_acknowledgment()` — deterministic pattern matching |
| `app/workflows/base_workflow.py` | `emit_event()`, `add_message()`, conversation history |
| `app/workflows/session_manager.py` | `SessionManager` / `SessionState` — prompt queue, node tracking |
| `app/infrastructure/config/models.py` | `IntentMappingConfig.acknowledgment_intent_name` (line 330) |
| `app/infrastructure/events/buffer.py` | `WorkflowEventBuffer` — emit + flush events |
| `app/infrastructure/events/catalog.py` | `EventType` enum definitions |
| `app/infrastructure/events/publisher.py` | `EventPublisher` — publishes to Redis + OTel spans |
| `app/api/routers/sessions/sse.py` | SSE streaming endpoint (delivers events to client) |
| `app/models/intent_graph.py` | `IntentNode` data model |

### Worker (emergingtech-tipai-ecmp-worker/)

| File | Role in ACK Flow |
|---|---|
| `app/intents/mock_thank_you_greetings.yaml` | Intent definition — system prompt, tools, policy, semantics |
| `app/tools/acknowledgment_handler.py` | `acknowledgment_handler_activity()` — follow-up detection, closure classification, LLM response |
| `app/tools/registry.py` | Tool registration (maps tool name to activity function) |
| `app/executor/workflow.py` | `AgentExecutorWorkflow` — executes the intent's tool |
| `app/executor/llm.py` | `get_completion()` — LLM call wrapper |

---

## 6 — Configuration Reference

### Orchestrator Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `ACK_DETECTION_ENABLED` | `true` | Master switch for deterministic ACK detection |
| `ACK_DETECTION_SELECTION_STRATEGY` | `round_robin` | Response template rotation strategy |

### Config Model

```python
# app/infrastructure/config/models.py, line 324
class IntentMappingConfig(BaseModel):
    acknowledgment_intent_name: str = "chat/mock_thank_you_greetings"
```

### Worker Intent Policy

```yaml
# mock_thank_you_greetings.yaml
policy:
  max_steps: 1           # Single tool execution
  max_react_loops: 0     # Direct execution, no planner loop
  timeout_seconds: 30    # Fast response budget
  rate_limit_rps: 10     # High rate for quick closures
```

---

## 7 — What Does NOT Happen on the ACK Path

Understanding what is **skipped** is as important as what runs:

| Component | Normal Pipeline | ACK Path |
|---|---|---|
| LLM intent mapping (`_map_prompt_to_graph`) | Called — ~150-250 tokens | **Skipped** |
| Query decomposition | Called | **Skipped** |
| Embedding-based intent retrieval | Called | **Skipped** |
| Graph construction | Called | **Skipped** |
| Intent scoring / ranking | Called | **Skipped** |
| `INTENT_MAPPING_COMPLETED` event | Emitted | **Not emitted** |
| Worker dispatch via Nexus | Yes | **Yes** (still dispatches) |
| Worker LLM call | Yes (heavy — RAG + generation) | **Yes** (lightweight — short closure response) |

**Cost savings per ACK message:**
- Orchestrator LLM tokens saved: ~200 tokens (intent mapping)
- Worker LLM is still called but uses a minimal prompt (~100 tokens vs ~500 for full RAG pipeline)
- Net savings: **~500 tokens per ACK message**

---

## 8 — Known Issues and Gaps

### Greetings Misclassified as ACKs

`"Hi"`, `"Hello"`, `"Hey"`, `"Good morning"` are currently in `PURE_ACK_TOKENS` / `PURE_ACK_PHRASES`. The reference test spec expects them to route to LLM, not be intercepted as ACKs. Greetings open a conversation; acknowledgments close or continue one.

**Impact:** Greetings get routed to `mock_thank_you_greetings` worker instead of receiving a proper greeting response from the LLM.

**Fix:** Remove `"hi"`, `"hello"`, `"hey"`, `"morning"`, `"afternoon"`, `"evening"` from `PURE_ACK_TOKENS` and `"good morning"`, `"good afternoon"`, `"good evening"` from `PURE_ACK_PHRASES`.

### Missing Composite Tokens

`"alright"` and `"roger"` are not in `PURE_ACK_TOKENS`, so composite messages like `"Alright, perfect"` and `"roger that, thanks"` fall through to LLM intent mapping instead of being caught deterministically.

**Fix:** Add `"alright"`, `"roger"` to `PURE_ACK_TOKENS` and `"roger that"` to `PURE_ACK_PHRASES`.

### No PURE_ACK Event Emission

The reference test spec documents an `intent_mapping_completed` event with `method: PURE_ACK`. The current codebase does not emit this — router mode bypasses intent mapping entirely, producing no mapping event. This makes it harder to distinguish ACK-routed messages from other router-mode messages in telemetry.

### Worker Still Makes an LLM Call

Even though the orchestrator saves LLM tokens by skipping intent mapping, the worker's `acknowledgment_handler_activity` still calls the LLM to generate a response. For truly zero-LLM handling, the orchestrator could return a canned response directly without dispatching to a worker at all.

---

> **See also:**
> - [[GENERAL_ACK Test Results]] — Test matrix for all 18 scenarios
> - [[TIP-AI Architecture Overview]] — Full system architecture
