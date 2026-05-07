# End-to-End Call Trace: "Can I get the towels" (REST-Sync Mode)

> **Request:** `POST /v1/sessions/{session_id}/messages`
> **Body:** `{ "prompt": "Can I get the towels" }`
> **Event Mode:** `rest-sync`

---

## Architecture Overview

```
Client (HTTP POST)
  │
  ▼
FastAPI Router (messaging.py)
  │
  ▼
Temporal Workflow Update (OrchestratorWorkflow.send_message_and_wait)
  │
  ├── Guardrail Check (activity: check_guardrail)
  ├── Ack Detection (ack_detector.detect_acknowledgement) → NOT an ack ("can" = request signal)
  ├── Slot Filling Check (_try_handle_slot_filling)
  └── Intent Mapping Pipeline
       ├── Decomposition (LLM call via PromptMapper._decompose_prompt)
       ├── Intent Search (IntentSearchService: keyword + pattern + embedding)
       └── Graph Generation (LLM call via PromptMapper._generate_graph_mapping)
  │
  ▼
Node Scheduling & Execution (NodeScheduler → ChildWorkflowManager)
  │
  ▼
Nexus RPC Call → ECMP Worker (IntentRuntimeServiceHandler.StartJob)
  │
  ▼
AgentExecutorWorkflow (ReAct loop: plan → tool → reflect)
  │
  ▼
Response Aggregation (SummaryGenerator → agent_conversationAggregator LLM)
  │
  ▼
REST Response (V1MessageResponse)
```

---

## Step-by-Step Call Trace

### Phase 1: HTTP Entry Point

| # | Class / Function | File | Details |
|---|---|---|---|
| 1 | `send_message_v1()` | `app/api/routers/sessions/messaging.py:141` | FastAPI endpoint receives POST. Extracts `session_id` from path, parses `V1MessageRequest` body (prompt, shadow_mode, ui_context, node_id). |
| 2 | `FeatureFlagService.evaluate_bool()` | `app/api/feature_flags/service.py` | Evaluates `sessions.messages` feature gate via Harness provider. If blocked → 403. |
| 3 | `validate_correlation_id()` | `app/api/utils.py` | Validates optional `X-Correlation-ID` header (max 128 chars, alphanumeric + `._:-`). |
| 4 | `check_duplicate_prompt()` | `app/api/utils.py` | Checks in-memory `_RECENT_PROMPTS` dict for duplicate prompt hash. If duplicate → returns same `message_id`. |
| 5 | `temporal_client.get_workflow_handle()` | `messaging.py:207` | Gets Temporal workflow handle for session. Raises 404 if session not found. |
| 6 | `handle.query("get_event_mode")` | `messaging.py:219` | Queries workflow for event mode. Returns `"rest-sync"` for this session. |
| 7 | `send_message_blocking()` | `messaging.py:37` | Called because `event_mode == "rest-sync"` and `node_id` is None. |

### Phase 2: Temporal Workflow Update (Blocking)

| # | Class / Function | File | Details |
|---|---|---|---|
| 8 | `handle.execute_update("send_message_and_wait", ...)` | `messaging.py:68` | Calls Temporal workflow update with args: `[prompt, message_id, shadow_mode, ui_context_dict, correlation_id, bearer_token]`. Blocks with `rpc_timeout` from config. |
| 9 | `OrchestratorWorkflow.send_message_and_wait()` | `orchestrator_workflow.py:665` | `@workflow.update` handler. Resets interrupt state, stores UI context, sets message context on event buffer. |
| 10 | `SessionManager.add_new_prompt()` | `session_manager.py:503` | Adds `{"prompt": "Can I get the towels", "shadow_mode": false}` to `pending_new_prompts` queue. |
| 11 | `SessionManager.increment_turn_counter()` | `session_manager.py:530` | Increments turn counter (e.g., → 1). Used for rolling conversation history. |
| 12 | `BaseWorkflow.add_message()` | `base_workflow.py` | Adds user message to `ConversationHistory` with `role="user"`, `source="user_input"`, `turn_number`. |
| 13 | `workflow.wait_condition(lambda: not has_pending_prompts())` | `orchestrator_workflow.py:745` | Waits up to 30s for prompt processing to complete. |

### Phase 3: Prompt Processing Pipeline

The main run loop (`_run_orchestration_cycle`) picks up the pending prompt via `_process_pending_prompts()`.

| # | Class / Function | File | Details |
|---|---|---|---|
| 14 | `_process_pending_prompts()` | `orchestrator_workflow.py:1112` | Pops prompt from queue. Runs guardrail → ack detection → slot filling → intent mapping pipeline. |
| 15 | `_check_input_guardrail()` | `orchestrator_workflow.py:1210` | Executes `check_guardrail` activity with `stage="user_input"`. If blocked → increments hit count, emits guardrail event, returns. For "Can I get the towels" → passes (not harmful). |
| 16 | `_prepare_prompt_for_processing()` | `orchestrator_workflow.py:1237` | Clears previous slot evaluation result. Updates `session.user_prompt`. Increments slot attempt counters. |
| 17 | `detect_acknowledgement("Can I get the towels")` | `app/intent_mapping/ack_detector.py:183` | **Result: NOT an ack.** Normalizes text → `"can i get the towels"`. Token `"can"` is in `REQUEST_SIGNALS` → `_has_request_signal()` returns True → returns `_NOT_ACK`. Pipeline continues. |
| 18 | `_try_handle_slot_filling()` | `orchestrator_workflow.py` | Checks if prompt fills slots for any `IncompleteNode`. For first message → no incomplete nodes → returns False. |
| 19 | `_process_prompt_as_new_intent()` | `orchestrator_workflow.py:1331` | Not router mode → proceeds to intent mapping. Calls `_get_high_level_conversation()` for context. |

### Phase 4: Intent Mapping (Temporal Activity)

| # | Class / Function | File | Details |
|---|---|---|---|
| 20 | `IntentMapper.map_prompt_to_graph()` | `orchestrator_components/intent_mapper.py:23` | Static method. Calls `workflow.execute_activity(ToolActivities.agent_mapPromptToGraph, ...)`. |
| 21 | `ToolActivities.agent_mapPromptToGraph()` | `app/activities/tool_activities.py:138` | `@activity.defn` wrapper. Delegates to standalone `agent_mapPromptToGraph()` function. |
| 22 | `agent_mapPromptToGraph()` | `app/activities/intent_mapping.py:59` | Main activity. Sets OTel session/message context. Sets `PrincipalContext` for AOS compliance. |
| 23 | `PromptMapper.__init__()` | `app/intent_mapping/prompt_mapper.py:37` | Creates mapper with `IntentSearchService`, `GraphProcessor`, `JsonProcessor`. |
| 24 | `PromptMapper.map_prompt_to_graph()` | `prompt_mapper.py:47` | Orchestrates the 4-step mapping flow. |

#### Step 4a: Decomposition (LLM Call #1)

| # | Class / Function | File | Details |
|---|---|---|---|
| 25 | `PromptMapper._decompose_prompt()` | `prompt_mapper.py:271` | Builds decomposition prompt via `build_decomposition_prompt()`. Calls `get_completion()` (LiteLLM). Parses JSON array of sub-queries. For "Can I get the towels" → likely returns `["Can I get the towels"]` (single atomic query). |

#### Step 4b: Intent Search

| # | Class / Function | File | Details |
|---|---|---|---|
| 26 | `IntentSearchService.get_active_intents()` | `intent_search_service.py:456` | When `bypass_intent_similarity=True` (default): fetches all active intents from registry (limit=50), optionally filtered by `team`. |
| 27 | `IntentRegistryClient.get_active_intents()` | `app/registry/client.py` | Queries PostgreSQL `intents` table for `status='active'` intents. Returns `List[AgentIntent]`. |
| 28 | `IntentSearchService.format_intents_for_llm()` | `intent_search_service.py:383` | Formats each intent as `"id: {id} \| name: {name} \| desc: {description}"`. All sub-queries get the same full intent list. |

#### Step 4c: Graph Generation (LLM Call #2)

| # | Class / Function | File | Details |
|---|---|---|---|
| 29 | `PromptMapper._generate_graph_mapping()` | `prompt_mapper.py:353` | Builds mapping prompt with `build_mapping_prompt()`. Sends sub-query/intent pairs to LLM. LLM returns JSON DAG with nodes. |
| 30 | `JsonProcessor.sanitize_response()` | `app/intent_mapping/json_utils.py` | Strips markdown fences, fixes common JSON issues. |
| 31 | `JsonProcessor.parse_json_safely()` | `json_utils.py` | Parses JSON with fallback strategies. |
| 32 | `JsonProcessor.validate_graph_structure()` | `json_utils.py` | Validates nodes have required fields (id, intent_id, params). |

#### Step 4d: Graph Construction

| # | Class / Function | File | Details |
|---|---|---|---|
| 33 | `PromptMapper._process_graph_structure()` | `prompt_mapper.py:392` | Calls `GraphProcessor.merge_nodes_by_intent()` to deduplicate. |
| 34 | `GraphProcessor.build_intent_graph()` | `app/intent_mapping/graph_processor.py` | Builds `IntentGraph` with `IntentNode` objects. |
| 35 | `IntentMapper.create_intent_graph_from_mapping()` | `intent_mapper.py:80` | Back in workflow. Parses activity result into `IntentGraph` with `IntentNode` and `UnknownIntentNode` lists. |

### Phase 5: Node Registration & Scheduling

| # | Class / Function | File | Details |
|---|---|---|---|
| 36 | `_add_nodes_from_intent_graph()` | `orchestrator_workflow.py` | Calls `SessionManager.add_nodes()`. Generates unique IDs: `n{intent_id}_f{execution_count}` (e.g., `n5_f1`). Stores `node_prompt` mapping. Emits `INTENT_MAPPING_COMPLETED` event. |
| 37 | `SessionManager.add_nodes()` | `session_manager.py:276` | Two-pass: (1) assigns unique IDs, (2) remaps dependencies. Stores in `state.nodes_by_id`. |
| 38 | `NodeScheduler.get_ready_nodes()` | `orchestrator_components/node_scheduler.py:37` | Finds nodes where all dependencies are in `completed` list and node not yet started. For single node → immediately ready. |

### Phase 6: Nexus Dispatch to ECMP Worker

| # | Class / Function | File | Details |
|---|---|---|---|
| 39 | `_start_ready_nodes()` | `orchestrator_workflow.py:2105` | For each ready node: builds `CombinedInput`, resolves executor model, starts child workflow via Nexus. |
| 40 | `ChildWorkflowManager.build_combined_input()` | `child_workflow_manager.py:406` | Fetches full intent from DB via `get_intent_by_id` activity. Builds `CombinedInput` with `AgentIntentWorkflowParams` (conversation_summary, prompt_queue, filtered_messages). |
| 41 | `ChildWorkflowManager.start_child_workflow()` | `child_workflow_manager.py:546` | Builds `JobRequest.with_principal_context()`. Creates `nexus_client` via `workflow.create_nexus_client(endpoint, service="IntentRuntimeService")`. Emits `NODE_SCHEDULED` event. Calls `nexus_client.start_operation("StartJob", job_request)`. |
| 42 | `NodeScheduler.add_in_flight()` / `mark_started()` | `node_scheduler.py:80/67` | Tracks the async task and marks node as started. |

### Phase 7: ECMP Worker — Nexus Handler

| # | Class / Function | File | Details |
|---|---|---|---|
| 43 | `IntentRuntimeServiceHandler.StartJob()` | `ecmp-worker/app/integration/nexus/handler.py:185` | `@nexus.workflow_run_operation`. Receives `JobRequest`. Calls `runtime.resolve_intent(req.agent)` to get `IntentDefinition` from YAML. |
| 44 | `IntentRuntime.resolve_intent()` | `ecmp-worker/app/executor/runtime.py` | Looks up intent name in loaded YAML definitions (`app/intents/*.yaml`). Returns `IntentDefinition` with tools, policy, prompts. |
| 45 | `ctx.start_workflow(AgentExecutorWorkflow, args=[req, intent_def], ...)` | `handler.py:254` | Starts `AgentExecutorWorkflow` on the executor task queue. |

### Phase 8: ECMP Worker — Agent Executor Workflow (ReAct Loop)

| # | Class / Function | File | Details |
|---|---|---|---|
| 46 | `AgentExecutorWorkflow.run()` | `ecmp-worker/app/executor/workflow.py:68` | `@workflow.defn`. Initializes from `JobRequest` + `IntentDefinition`. Sets up `ExecutionState`, `ConversationHistory`, `PromptManager`. |
| 47 | `_initialize_from_policy()` | `workflow.py` | Applies intent policy: `max_react_loops`, `max_tool_retries`, `executor_history_limit`, tool definitions. |
| 48 | `PromptManager.build_system_prompt()` | `ecmp-worker/app/executor/prompt_manager.py` | Builds system prompt from intent definition, available tools, conversation context. |
| 49 | **ReAct Loop iteration** | `workflow.py` | Repeats up to `max_react_loops` (default 3): |
| 50 | `agent_tool_planner` activity | `ecmp-worker/app/executor/activities/tool_activities.py` | LLM call #3: Given system prompt + conversation history, LLM decides next action (tool call or final answer). |
| 51 | `execute_tool()` | `ecmp-worker/app/executor/workflow_activity_dispatch.py` | Dispatches tool execution. Routes to the matching tool binding (e.g., `mock_hotel_search`, `respond_acknowledgement`, `policy_qa`). |
| 52 | Tool Activity (e.g., `mock_hotel_search`) | `ecmp-worker/app/tools/activities/` | Executes the actual tool logic. Returns structured result. |
| 53 | LLM Reflection | `workflow.py` | LLM reviews tool result. Decides: call another tool, ask user question, or produce final answer. |
| 54 | `JobSnapshot` returned | `workflow.py` | When loop completes: builds `JobSnapshot(status="DONE", result={messages, tool_results})`. |

### Phase 9: Result Collection in Orchestrator

| # | Class / Function | File | Details |
|---|---|---|---|
| 55 | `_await_child_completions()` | `orchestrator_workflow.py` | Awaits in-flight async tasks. For each completed task: |
| 56 | `ChildWorkflowManager.convert_job_snapshot_to_orchestrator_result()` | `child_workflow_manager.py:36` | Converts executor `JobSnapshot` → orchestrator result format. Extracts `messages` list, checks for guardrail blocks. |
| 57 | `aggregate_child_messages()` | `orchestrator_workflow.py:3519` | Parses child result using `parse_child_result()`, `extract_messages_from_child()`, `process_child_messages()`. Adds to `ConversationHistory`. |
| 58 | `SessionManager.set_node_result()` | `session_manager.py:373` | Stores result in `state.node_results[node_id]`. |
| 59 | `NodeScheduler.mark_completed()` | `node_scheduler.py:54` | Marks node as completed. Triggers ready-check for dependent nodes. |
| 60 | Emits `NODE_COMPLETED` event | `orchestrator_workflow.py` | Via `WorkflowEventBuffer`. |

### Phase 10: Response Aggregation (LLM Call #4)

| # | Class / Function | File | Details |
|---|---|---|---|
| 61 | `_handle_session_cycle_completion()` | `orchestrator_workflow.py:2241` | Checks all nodes complete. If yes → calls `_produce_final_summary()`. |
| 62 | `_produce_final_summary()` | `orchestrator_workflow.py:3099` | Determines aggregation strategy (LLM vs concatenation vs static fallback). For `llm_aggregation=True` → calls `SummaryGenerator.generate_final_summary()`. |
| 63 | `SummaryGenerator.generate_final_summary()` | `orchestrator_components/summary_generator.py` | Calls `workflow.execute_activity(agent_conversationAggregator, ...)`. |
| 64 | `agent_conversationAggregator()` | `app/activities/llm_activities.py:96` | Builds aggregator prompt via `build_aggregator_system_prompt()` + `build_aggregator_user_prompt()`. Calls `get_completion()` (LiteLLM). Returns synthesized natural language response. |
| 65 | Output guardrail check | `orchestrator_workflow.py:3223` | If guardrails enabled, runs `_check_output_guardrail()` on aggregator response. |
| 66 | `SessionManager.set_node_result("__final_summary", ...)` | `orchestrator_workflow.py:3275` | Stores final summary as special node result. This unblocks the `wait_condition` in step 13. |
| 67 | `_emit_agent_response()` | `orchestrator_workflow.py` | Adds agent response to `ConversationHistory`. Emits `AGENT_RESPONSE` SSE event. |

### Phase 11: REST Response Assembly

| # | Class / Function | File | Details |
|---|---|---|---|
| 68 | `workflow.wait_condition` unblocks | `orchestrator_workflow.py:771` | `__final_summary` is now set → condition satisfied. |
| 69 | `_get_response_for_completion()` | `orchestrator_workflow.py:3461` | Extracts: (1) aggregator response text from `__final_summary`, (2) intent mapping from `SessionManager`, (3) per-node result tuples via `parse_executor_result()` + `build_node_result_tuples()`. |
| 70 | Update handler returns dict | `orchestrator_workflow.py:794` | Returns `{"response": "...", "intent_mapping": {...}, "node_results": {...}}`. |
| 71 | `send_message_blocking()` receives result | `messaging.py:68` | `handle.execute_update()` returns the dict. |
| 72 | `IntentRegistryClient.get_intent_by_id()` | `messaging.py:84` | Enhances `intent_details` with human-readable `label` (agent_name) from registry. |
| 73 | `handle.query("get_user_facing_conversation_history")` | `messaging.py:100` | Queries for `incomplete_nodes` state (for slot filling UI). |
| 74 | `V1MessageResponse(...)` | `messaging.py:105` | Constructs final API response model with: `accepted`, `message_id`, `model_version`, `taxonomy_version`, `response`, `intent_mapping`, `node_results`, `incomplete_nodes`. |

---

## LLM Calls Summary

| # | Purpose | Where | Model Config Key |
|---|---|---|---|
| 1 | Decomposition | `PromptMapper._decompose_prompt()` | `decomposition_model` |
| 2 | Intent Mapping | `PromptMapper._generate_graph_mapping()` | `intent_mapping_model` |
| 3 | Tool Planning (executor) | `agent_tool_planner` activity in ECMP worker | `executor_model` |
| 4 | Aggregation | `agent_conversationAggregator` activity | `aggregator_model` |

---

## Key Classes Reference

| Class | Repository | File | Role |
|---|---|---|---|
| `V1MessageRequest` | orchestrator | `app/models/api_requests.py` | Request body model |
| `V1MessageResponse` | orchestrator | `app/models/api_responses.py` | Response model |
| `OrchestratorWorkflow` | orchestrator | `app/workflows/orchestrator_workflow.py` | Main Temporal workflow |
| `SessionManager` | orchestrator | `app/workflows/session_manager.py` | Session state management |
| `NodeScheduler` | orchestrator | `app/workflows/orchestrator_components/node_scheduler.py` | Dependency-aware scheduling |
| `IntentMapper` | orchestrator | `app/workflows/orchestrator_components/intent_mapper.py` | Workflow-level intent mapping |
| `ChildWorkflowManager` | orchestrator | `app/workflows/orchestrator_components/child_workflow_manager.py` | Nexus dispatch to workers |
| `SummaryGenerator` | orchestrator | `app/workflows/orchestrator_components/summary_generator.py` | Final response aggregation |
| `ToolActivities` | orchestrator | `app/activities/tool_activities.py` | Temporal activity wrapper |
| `PromptMapper` | orchestrator | `app/intent_mapping/prompt_mapper.py` | Decompose + map + graph |
| `IntentSearchService` | orchestrator | `app/intent_mapping/intent_search_service.py` | Registry search (keyword/pattern/embedding) |
| `IntentRegistryClient` | orchestrator | `app/registry/client.py` | PostgreSQL intent queries |
| `AckDetectionResult` | orchestrator | `app/intent_mapping/ack_detector.py` | Deterministic ack classifier |
| `IntentRuntimeServiceHandler` | ecmp-worker | `app/integration/nexus/handler.py` | Nexus service handler |
| `IntentRuntime` | ecmp-worker | `app/executor/runtime.py` | Intent resolution from YAML |
| `AgentExecutorWorkflow` | ecmp-worker | `app/executor/workflow.py` | ReAct loop executor |
| `PromptManager` | ecmp-worker | `app/executor/prompt_manager.py` | System prompt builder |
| `JobRequest` / `JobSnapshot` | ecmp-worker | `app/executor/contracts.py` | Nexus data contracts |

---

## Ack Detection Detail for "Can I get the towels"

**Input:** `"Can I get the towels"`

1. `detect_acknowledgement()` → `_normalize()` → `"can i get the towels"`
2. `_is_all_ack_tokens("can i get the towels")` → tries greedy match → `"can"` is NOT in `ACK_TOKENS` → returns `None`
3. Even if tokens partially matched, `_has_request_signal("Can I get the towels")` → word `"can"` is in `REQUEST_SIGNALS` → returns `True`
4. **Result:** `AckDetectionResult(is_ack=False)` → proceeds to full intent mapping pipeline

---

## Event Sequence (SSE/REST)

```
1. INTENT_MAPPING_COMPLETED  (node_count, intent_details)
2. NODE_SCHEDULED            (node_id)
3. NEXUS_CALL_STARTED        (node_id, endpoint, service)
4. NEXUS_CALL_COMPLETED      (node_id, latency_ms, job_status)
5. NODE_COMPLETED            (node_id)
6. AGENT_RESPONSE            (final aggregated response text)
```
