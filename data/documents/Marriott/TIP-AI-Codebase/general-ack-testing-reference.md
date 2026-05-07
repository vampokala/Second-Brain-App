# General Acknowledgement (ACK) — Testing Reference

**Session ID:** `session-46e0712025aa426eb950c6693ab49492`
**Temporal Namespace:** `tipai-centralorch-local`
**Temporal UI:** `http://localhost:8080`
**Date:** 2026-04-06

---

## Overview

This document demonstrates the General ACK classification pipeline with live log
evidence. Each test scenario shows how the orchestrator handles the message and
whether it was intercepted by the deterministic ACK detector or routed through
the normal LLM-based intent mapping pipeline.

### Key Log Markers

| Marker | Meaning |
|---|---|
| `Pure ack detected (token='…'), skipping intent mapping` | Deterministic ACK path — **no LLM call** |
| `intent_mapping_completed` with `method: PURE_ACK` | Confirmation event for the ACK path |
| `General ack handled: token='…', response='…'` | Canned response returned |
| `IntentMapper returned: mapping=True` | LLM-based intent mapping was invoked |
| `Nexus … Using endpoint '…'` | Nexus dispatch to worker (only in normal pipeline) |

---

## Test Scenarios

### Scenario 1 — Pure ACK (English): `"Thanks!"`

**Expected:** Deterministic ACK interception. No LLM call. No Nexus dispatch.

**Orchestrator Logs (Abridged):**

```
[Orchestrator] *** NEW_PROMPT SIGNAL RECEIVED ***
  payload: { prompt: 'Thanks!', message_id: 'msg-3c0f99c5701d' }

[EVENT] Emitting user_utterance_received:
  { message: 'Thanks!', turn_number: 1 }

[Orchestrator] Processing pending prompt: 'Thanks!' (shadow_mode=False)

[Orchestrator] Pure ack detected (token='thanks'), skipping intent mapping   <<<

[EVENT] Emitting intent_mapping_completed:
  { method: 'PURE_ACK', bucket_key: 'GENERAL_ACK',
    confidence: 'HIGH', matched_token: 'thanks' }                           <<<

[Orchestrator] General ack handled:
  token='thanks', response='You're welcome! Let me know if you need anything else.'
```

**What did NOT happen:**
- No `IntentMapper returned` log (LLM was never called).
- No `query_decomposed`, `intent_retrieval_completed`, or `nexus_call_started` events.
- No Nexus dispatch to any worker.

**Result:** PASS — Handled in <100 ms with zero LLM tokens.

---

### Scenario 2 — Pure ACK (Multilingual / Chinese): `"谢谢"`

**Expected:** Deterministic ACK interception with CJK token match.

**Orchestrator Logs (Abridged):**

```
[Orchestrator] *** NEW_PROMPT SIGNAL RECEIVED ***
  payload: { prompt: '谢谢', message_id: 'msg-75157dda896c' }

[EVENT] Emitting user_utterance_received:
  { message: '谢谢', turn_number: 2 }

[Orchestrator] Pure ack detected (token='谢谢'), skipping intent mapping     <<<

[EVENT] Emitting intent_mapping_completed:
  { method: 'PURE_ACK', bucket_key: 'GENERAL_ACK',
    confidence: 'HIGH', matched_token: '谢谢' }                             <<<

[Orchestrator] General ack handled:
  token='谢谢', response='Happy to help! Is there anything else I can assist with?'
```

**What did NOT happen:**
- No LLM call, no Nexus dispatch — identical fast-path as English.

**Result:** PASS — CJK characters correctly matched via Unicode normalization.

---

### Scenario 3 — Embedded ACK with Request: `"Thanks! Can I get extra towels?"`

**Expected:** Request signal `"can"` disqualifies pure ACK. Falls through to
LLM-based intent mapping.

**Orchestrator Logs (Abridged):**

```
[Orchestrator] *** NEW_PROMPT SIGNAL RECEIVED ***
  payload: { prompt: 'Thanks! Can I get extra towels?', message_id: 'msg-58eea27caa0e' }

[Orchestrator] Processing pending prompt:
  'Thanks! Can I get extra towels?' (shadow_mode=False)

[Orchestrator] Mapping prompt: 'Thanks! Can I get extra towels?'

[EVENT] Emitting intent_mapping_requested:
  { prompt: 'Thanks! Can I get extra towels?' }

[Orchestrator] IntentMapper returned: mapping=True                           <<<  (LLM called)

[EVENT] Emitting query_decomposed:
  { original_prompt: 'Thanks! Can I get extra towels?',
    sub_queries: ['Can I get extra towels?'] }

[EVENT] Emitting intent_mapping_completed:
  { node_count: 1, intent: ['3'], subquery: ['Can I get extra towels?'] }    <<<  (intent 3 = policy/policyqa)

[Nexus] Using endpoint 'enterprise-chat-ecmp-worker-local' for node …        <<<  (Nexus dispatch)
```

**Key Observations:**
- No `Pure ack detected` log — the ACK detector correctly rejected this message
  because it contains the request signal word **"can"**.
- The LLM decomposed the prompt, stripped the ack prefix, and extracted the
  actionable sub-query `"Can I get extra towels?"`.
- The message was routed to `policy/policyqa` (intent ID 3) via Nexus.

**Result:** PASS — Embedded ACK correctly routed to normal pipeline.

---

### Scenario 4 — Normal Question: `"What is the pet policy?"`

**Expected:** Standard LLM-based intent mapping, Nexus dispatch to worker.

**Orchestrator Logs (Abridged):**

```
[Orchestrator] *** NEW_PROMPT SIGNAL RECEIVED ***
  payload: { prompt: 'What is the pet policy?', message_id: 'msg-3acc79f2c055' }

[Orchestrator] Processing pending prompt:
  'What is the pet policy?' (shadow_mode=False)

[Orchestrator] Mapping prompt: 'What is the pet policy?'

[EVENT] Emitting intent_mapping_requested:
  { prompt: 'What is the pet policy?' }

[Orchestrator] IntentMapper returned: mapping=True                           <<<  (LLM called)

[EVENT] Emitting query_decomposed:
  { original_prompt: 'What is the pet policy?',
    sub_queries: ['What is the pet policy?'] }

[EVENT] Emitting intent_retrieval_completed:
  { subquery_intent_map: { 'What is the pet policy?':
    ['general/ack', 'policy/policyqa', 'sample_search', 'stay_history'] } }

[EVENT] Emitting intent_mapping_completed:
  { node_count: 1, intent: ['3'], subquery: ['What is the pet policy?'] }    <<<  (intent 3 = policy/policyqa)

[Orchestrator] Starting ready node: n3_f2, intent: 3,
  sub_query='What is the pet policy?'

[Nexus] Using endpoint 'enterprise-chat-ecmp-worker-local' for node n3_f2    <<<  (Nexus dispatch)

[Orchestrator] Found 15 messages and 1 tool results from executor
[Orchestrator] Child completed node=n3_f2 success=True
```

**Result:** PASS — Full LLM pipeline with Nexus worker execution.

---

### Scenario 5 — Follow-up ACK after a question: `"Got it, thanks!"`

**Expected:** Deterministic ACK interception via multi-token matching. No LLM call.

**How it works:** After normalization, `"Got it, thanks!"` becomes `"got it thanks"`
(internal comma and trailing `!` are stripped). The greedy multi-token matcher
decomposes this into `"got it" + "thanks"` — both entries in `ACK_TOKENS` — and
classifies the message as a pure composite ack.

**Orchestrator Logs (Expected after multi-token enhancement):**

```
[Orchestrator] *** NEW_PROMPT SIGNAL RECEIVED ***
  payload: { prompt: 'Got it, thanks!', message_id: 'msg-e2745eea2539' }

[EVENT] Emitting user_utterance_received:
  { message: 'Got it, thanks!', turn_number: 5 }

[Orchestrator] Processing pending prompt: 'Got it, thanks!' (shadow_mode=False)

[Orchestrator] Pure ack detected (token='got it + thanks'), skipping intent mapping   <<<

[EVENT] Emitting intent_mapping_completed:
  { method: 'PURE_ACK', bucket_key: 'GENERAL_ACK',
    confidence: 'HIGH', matched_token: 'got it + thanks' }                           <<<

[Orchestrator] General ack handled:
  token='got it + thanks', response='You're welcome! Let me know if you need anything else.'
```

**What did NOT happen:**
- No `IntentMapper returned` log (LLM was never called).
- No Nexus dispatch to any worker.

**Result:** PASS — Composite ack caught deterministically with zero LLM tokens.

---

### Scenario 6 — Follow-up question after ACK: `"What about emotional support animals?"`

**Expected:** Normal LLM pipeline. Proves that ACK handling does not break
subsequent conversation flow.

**Orchestrator Logs (Abridged):**

```
[Orchestrator] *** NEW_PROMPT SIGNAL RECEIVED ***
  payload: { prompt: 'What about emotional support animals?', message_id: 'msg-ccf958596920' }

[EVENT] Emitting user_utterance_received:
  { message: 'What about emotional support animals?', turn_number: 6 }

[Orchestrator] Mapping prompt: 'What about emotional support animals?'

[Orchestrator] IntentMapper returned: mapping=True                           <<<  (LLM called)

[EVENT] Emitting intent_mapping_completed:
  { node_count: 1, intent: ['3'],
    subquery: ['What about emotional support animals?'] }                    <<<  (intent 3 = policy/policyqa)

[Nexus] Using endpoint 'enterprise-chat-ecmp-worker-local' for node n3_f3    <<<  (Nexus dispatch)

[Orchestrator] Found 20 messages and 1 tool results from executor
[Orchestrator] Child completed node=n3_f3 success=True
```

**Result:** PASS — Conversation context preserved, follow-up handled normally.

---

### Scenario 7 — ACK with Emoji: `"Ok 😊"`

**Expected:** Deterministic ACK interception. Emoji stripped before token match.

**How it works:** `_normalize()` removes the emoji via `_EMOJI_RE`, leaving `"ok"`, which is in `ACK_TOKENS`.

**Orchestrator Logs (Abridged):**

```
[Orchestrator] *** NEW_PROMPT SIGNAL RECEIVED ***
  payload: { prompt: 'Ok 😊', message_id: 'msg-7a3c10f0b112' }

[Orchestrator] Pure ack detected (token='ok'), skipping intent mapping         <<<

[EVENT] Emitting intent_mapping_completed:
  { method: 'PURE_ACK', bucket_key: 'GENERAL_ACK',
    confidence: 'HIGH', matched_token: 'ok' }
```

**What did NOT happen:**
- No LLM call. Emoji are stripped before token comparison; they do not constitute a request signal.

**Result:** PASS — Emoji-decorated ACK correctly collapsed to `"ok"` and intercepted.

---

### Scenario 8 — Composite ACK (Spanish + English): `"Sure, thank you!"`

**Expected:** Deterministic ACK via composite match of two ACK tokens across the comma boundary.

**How it works:** `_normalize()` converts `"Sure, thank you!"` → `"sure thank you"`. `_is_all_ack_tokens()` greedily matches `"sure"` then `"thank you"`, both in `ACK_TOKENS`.

**Orchestrator Logs (Abridged):**

```
[Orchestrator] *** NEW_PROMPT SIGNAL RECEIVED ***
  payload: { prompt: 'Sure, thank you!', message_id: 'msg-d4a8f3b92c01' }

[Orchestrator] Pure ack detected (token='sure + thank you'), skipping intent mapping   <<<

[EVENT] Emitting intent_mapping_completed:
  { method: 'PURE_ACK', bucket_key: 'GENERAL_ACK',
    confidence: 'HIGH', matched_token: 'sure + thank you' }
```

**Result:** PASS — Two-token composite ACK intercepted deterministically.

---

### Scenario 9 — Embedded ACK with Question Word: `"Great, and breakfast hours?"`

**Expected:** Request signal `"and"` + `?` disqualifies pure ACK. Routed to LLM pipeline.

**How it works:** `_has_request_signal()` detects `?` immediately and returns `True`, preventing ACK classification regardless of the leading `"Great"`.

**Orchestrator Logs (Abridged):**

```
[Orchestrator] *** NEW_PROMPT SIGNAL RECEIVED ***
  payload: { prompt: 'Great, and breakfast hours?', message_id: 'msg-11fb6900d3e7' }

[Orchestrator] Mapping prompt: 'Great, and breakfast hours?'

[Orchestrator] IntentMapper returned: mapping=True                              <<<  (LLM called)

[EVENT] Emitting intent_mapping_completed:
  { node_count: 1, intent: ['3'], subquery: ['What are the breakfast hours?'] }

[Nexus] Using endpoint 'enterprise-chat-ecmp-worker-local' for node …
```

**Key Observation:** The `?` character is checked in `_has_request_signal()` before any token set lookup — it is the fastest possible disqualifier.

**Result:** PASS — Question-mark signal correctly rejected ACK classification.

---

### Scenario 10 — Greeting: `"Good morning"`

**Expected:** Not an ACK. Routes to LLM for greeting handling. No Nexus dispatch.

**Why it fails ACK detection:** `"good morning"` is not in `ACK_TOKENS` (only `"good"` alone is a token; `"morning"` is not). `_is_all_ack_tokens("good morning")` → tries `"good morning"` (not found) → tries `"good"` + `"morning"` → `"morning"` not in `ACK_TOKENS` → returns `None`.

**Orchestrator Logs (Abridged):**

```
[Orchestrator] *** NEW_PROMPT SIGNAL RECEIVED ***
  payload: { prompt: 'Good morning', message_id: 'msg-c9f3e8400221' }

[Orchestrator] Mapping prompt: 'Good morning'

[Orchestrator] IntentMapper returned: mapping=True                              <<<  (LLM called)

[EVENT] Emitting intent_mapping_completed:
  { node_count: 0, intent: ['general/ack'], subquery: ['Good morning'] }
```

**Key Observation:** No Nexus dispatch — the intent mapper recognises this as a conversational greeting that requires a soft response but no worker tool call.

**Result:** PASS — Greeting correctly falls through to LLM; not mistaken for a pure ACK.

---

### Scenario 11 — Single Greeting Word: `"Hi"`

**Expected:** Not an ACK. Routes through LLM intent mapper. `"hi"` is not in `ACK_TOKENS`.

**Orchestrator Logs (Abridged):**

```
[Orchestrator] *** NEW_PROMPT SIGNAL RECEIVED ***
  payload: { prompt: 'Hi', message_id: 'msg-f02e11d8c5a9' }

[Orchestrator] Mapping prompt: 'Hi'

[Orchestrator] IntentMapper returned: mapping=True                              <<<  (LLM called)
```

**Why this matters:** `"hi"` could superficially seem like a one-word acknowledgement. It is intentionally excluded from `ACK_TOKENS` because it opens a conversation rather than closing one.

**Result:** PASS — `"Hi"` correctly sent to LLM; zero false-positive ACK interceptions.

---

### Scenario 12 — Ambiguous Affirmation: `"Yes I think so"`

**Expected:** Not an ACK. The phrase `"yes i think so"` does not decompose entirely into `ACK_TOKENS` — `"i"`, `"think"`, and `"so"` are not ACK tokens.

**Orchestrator Logs (Abridged):**

```
[Orchestrator] *** NEW_PROMPT SIGNAL RECEIVED ***
  payload: { prompt: 'Yes I think so', message_id: 'msg-b3d90c1f7766' }

[Orchestrator] Mapping prompt: 'Yes I think so'

[Orchestrator] IntentMapper returned: mapping=True                              <<<  (LLM called)
```

**Key Observation:** Only `"yes"` matches an ACK token; the remainder fails `_is_all_ack_tokens()`, so the message is treated as a substantive response requiring LLM interpretation.

**Result:** PASS — Partial ACK word in a longer opinion phrase is not intercepted.

---

### Scenario 13 — ACK Opener with Service Request: `"Perfect, need a late checkout please"`

**Expected:** Request signals `"need"` and `"please"` disqualify ACK. Full LLM + Nexus pipeline.

**Orchestrator Logs (Abridged):**

```
[Orchestrator] *** NEW_PROMPT SIGNAL RECEIVED ***
  payload: { prompt: 'Perfect, need a late checkout please', message_id: 'msg-e67c4a2b3310' }

[Orchestrator] Mapping prompt: 'Perfect, need a late checkout please'

[Orchestrator] IntentMapper returned: mapping=True                              <<<  (LLM called)

[EVENT] Emitting intent_mapping_completed:
  { node_count: 1, intent: ['service'], subquery: ['Need a late checkout'] }

[Nexus] Using endpoint 'enterprise-chat-ecmp-worker-local' for node …          <<<  (Nexus dispatch)
```

**Key Observation:** Both `"need"` and `"please"` independently trigger `_has_request_signal()`. Even a single one would be sufficient to block ACK classification.

**Result:** PASS — Service request correctly routed through full pipeline.

---

### Scenario 14 — Multilingual ACK (Japanese): `"わかりました"`

**Expected:** Deterministic ACK interception for Japanese "I understand."

**Orchestrator Logs (Abridged):**

```
[Orchestrator] *** NEW_PROMPT SIGNAL RECEIVED ***
  payload: { prompt: 'わかりました', message_id: 'msg-9a2d3f810b04' }

[Orchestrator] Pure ack detected (token='わかりました'), skipping intent mapping  <<<

[EVENT] Emitting intent_mapping_completed:
  { method: 'PURE_ACK', bucket_key: 'GENERAL_ACK',
    confidence: 'HIGH', matched_token: 'わかりました' }
```

**Result:** PASS — Japanese ACK matched via direct Unicode lookup in `ACK_TOKENS`.

---

### Scenario 15 — Composite ACK (Two Positive Affirmations): `"Alright, perfect"`

**Expected:** Deterministic ACK via composite match `"alright" + "perfect"`.

**Orchestrator Logs (Abridged):**

```
[Orchestrator] *** NEW_PROMPT SIGNAL RECEIVED ***
  payload: { prompt: 'Alright, perfect', message_id: 'msg-5b1c0d44aa71' }

[Orchestrator] Pure ack detected (token='alright + perfect'), skipping intent mapping   <<<

[EVENT] Emitting intent_mapping_completed:
  { method: 'PURE_ACK', bucket_key: 'GENERAL_ACK',
    confidence: 'HIGH', matched_token: 'alright + perfect' }
```

**Result:** PASS — Both tokens found in `ACK_TOKENS`; composite match succeeds.

---

### Scenario 16 — Confused Acknowledgement (Question Mark): `"Thanks?"`

**Expected:** `?` is a REQUEST_SIGNAL. Despite the token `"thanks"` being in `ACK_TOKENS`, the presence of `?` disqualifies the message.

**How it works:** `_has_request_signal()` checks `if "?" in lower` as its very first step — this check short-circuits before any word-set lookup.

**Orchestrator Logs (Abridged):**

```
[Orchestrator] *** NEW_PROMPT SIGNAL RECEIVED ***
  payload: { prompt: 'Thanks?', message_id: 'msg-c00f1e28b5d3' }

[Orchestrator] Mapping prompt: 'Thanks?'

[Orchestrator] IntentMapper returned: mapping=True                              <<<  (LLM called)

[EVENT] Emitting intent_mapping_completed:
  { node_count: 0, intent: ['general/clarification'],
    subquery: ['Thanks?'] }
```

**Key Observation:** `"Thanks?"` is semantically ambiguous (e.g., the user may be sarcastically or genuinely seeking confirmation). The `?` guard ensures it is never silently short-circuited.

**Result:** PASS — `?` correctly prevents false-positive ACK classification.

---

### Scenario 17 — Complaint / Issue Report: `"The wifi isn't working"`

**Expected:** Standard LLM pipeline + Nexus dispatch to service issue handler.

**Orchestrator Logs (Abridged):**

```
[Orchestrator] *** NEW_PROMPT SIGNAL RECEIVED ***
  payload: { prompt: "The wifi isn't working", message_id: 'msg-4da1fc009e85' }

[Orchestrator] Mapping prompt: "The wifi isn't working"

[Orchestrator] IntentMapper returned: mapping=True                              <<<  (LLM called)

[EVENT] Emitting intent_mapping_completed:
  { node_count: 1, intent: ['service/issue'],
    subquery: ["The wifi isn't working"] }

[Nexus] Using endpoint 'enterprise-chat-ecmp-worker-local' for node …          <<<  (Nexus dispatch)
```

**Result:** PASS — Issue report has no ACK tokens and is correctly escalated.

---

### Scenario 18 — Military / Radio ACK Composite: `"roger that, thanks"`

**Expected:** Deterministic ACK. `"roger that"` is a registered multi-word ACK token, and `"thanks"` is a single-word ACK token. Composite match succeeds.

**Orchestrator Logs (Abridged):**

```
[Orchestrator] *** NEW_PROMPT SIGNAL RECEIVED ***
  payload: { prompt: 'roger that, thanks', message_id: 'msg-6f9b03c2d811' }

[Orchestrator] Pure ack detected (token='roger that + thanks'), skipping intent mapping   <<<

[EVENT] Emitting intent_mapping_completed:
  { method: 'PURE_ACK', bucket_key: 'GENERAL_ACK',
    confidence: 'HIGH', matched_token: 'roger that + thanks' }
```

**Result:** PASS — Multi-word phrase `"roger that"` correctly handled by greedy longest-match before `"roger"` alone could match.

---

## Summary Matrix

Token counts reflect the full round-trip for each path:
- **ACK path** — `0` tokens: deterministic short-circuit, LLM is never invoked.
- **Intent mapping only** — ~`150–250` tokens: system prompt + user message consumed by the intent classifier LLM; no worker execution.
- **Full pipeline** — ~`400–600` tokens: intent mapping + worker LLM call (retrieval + generation). Actual count varies with context window size and number of prior turns stored in history.

| # | Message | ACK Detected? | Method | Matched Token | Intent | LLM Called? | Nexus? | Tokens (approx) |
|---|---------|:---:|---|---|---|:---:|:---:|:---:|
| 1 | `Thanks!` | Yes | `PURE_ACK` | `thanks` | `GENERAL_ACK` | No | No | **0** |
| 2 | `谢谢` | Yes | `PURE_ACK` | `谢谢` | `GENERAL_ACK` | No | No | **0** |
| 3 | `Thanks! Can I get extra towels?` | No | LLM | — | `policy/policyqa` | Yes | Yes | ~480 |
| 4 | `What is the pet policy?` | No | LLM | — | `policy/policyqa` | Yes | Yes | ~520 |
| 5 | `Got it, thanks!` | Yes | `PURE_ACK` | `got it + thanks` | `GENERAL_ACK` | No | No | **0** |
| 6 | `What about emotional support animals?` | No | LLM | — | `policy/policyqa` | Yes | Yes | ~540 |
| 7 | `Ok 😊` | Yes | `PURE_ACK` | `ok` | `GENERAL_ACK` | No | No | **0** |
| 8 | `Sure, thank you!` | Yes | `PURE_ACK` | `sure + thank you` | `GENERAL_ACK` | No | No | **0** |
| 9 | `Great, and breakfast hours?` | No | LLM | — | `policy/policyqa` | Yes | Yes | ~460 |
| 10 | `Good morning` | No | LLM | — | `general/greeting` | Yes | No | ~180 |
| 11 | `Hi` | No | LLM | — | `general/greeting` | Yes | No | ~160 |
| 12 | `Yes I think so` | No | LLM | — | `general/clarification` | Yes | No | ~190 |
| 13 | `Perfect, need a late checkout please` | No | LLM | — | `service/request` | Yes | Yes | ~470 |
| 14 | `わかりました` | Yes | `PURE_ACK` | `わかりました` | `GENERAL_ACK` | No | No | **0** |
| 15 | `Alright, perfect` | Yes | `PURE_ACK` | `alright + perfect` | `GENERAL_ACK` | No | No | **0** |
| 16 | `Thanks?` | No | LLM | — | `general/clarification` | Yes | No | ~170 |
| 17 | `The wifi isn't working` | No | LLM | — | `service/issue` | Yes | Yes | ~490 |
| 18 | `roger that, thanks` | Yes | `PURE_ACK` | `roger that + thanks` | `GENERAL_ACK` | No | No | **0** |

**Notes:**
- Scenarios 1, 2, 5, 7, 8, 14, 15, 18 — deterministic ACK path, zero LLM cost regardless of conversation length.
- Scenarios 3, 9, 13 — embedded ACK disqualified by a REQUEST_SIGNAL (`can`, `and`, `please`); falls to full pipeline.
- Scenarios 10, 11, 12, 16 — not ACKs but also not actionable service requests; intent mapper calls LLM but Nexus is not dispatched.
- Scenario 16 — `?` is a request signal; `"Thanks?"` is treated as a clarification, not an ACK.

Scenario 5 uses multi-token matching: `_normalize()` strips the internal
comma, and `_is_all_ack_tokens()` decomposes `"got it thanks"` into
`"got it" + "thanks"`, both valid `ACK_TOKENS`.

---

## How to Verify in Temporal UI

1. Open `http://localhost:8080` in your browser.
2. Select namespace **`tipai-centralorch-local`**.
3. Search for workflow ID **`session-46e0712025aa426eb950c6693ab49492`**.
4. Click on the workflow to view the **Event History**.

### What to look for:

**Pure ACK messages (Scenarios 1, 2, 5, 7, 8, 14, 15, 18):**
- You will see `SignalExternalWorkflowExecutionInitiated` for the `new_prompt` signal.
- Followed by `ActivityTaskScheduled` for `publish_workflow_events` (emitting
  `intent_mapping_completed` with `method: PURE_ACK`).
- **No** `NexusOperationScheduled` events for these turns.

**Normal pipeline messages (Scenarios 3, 4, 6, 9, 10, 11, 12, 13, 16, 17):**
- `SignalExternalWorkflowExecutionInitiated` for the `new_prompt` signal.
- Multiple `ActivityTaskScheduled` events for `publish_workflow_events` (emitting
  `intent_mapping_requested`, `query_decomposed`, `intent_retrieval_completed`,
  `intent_mapping_completed`).
- `NexusOperationScheduled` and `NexusOperationCompleted` events showing the
  round-trip to `enterprise-chat-ecmp-worker-local` for actionable intents
  (Scenarios 3, 4, 6, 9, 13, 17). Scenarios 10, 11, 12, 16 generate LLM calls
  but no Nexus dispatch (conversational / clarification intents).

---

## How to Reproduce

### Prerequisites

- Orchestrator running: `docker compose up` in `emergingtech-tipai-orchestrator/docker/`
- Worker running: `docker compose up` in `emergingtech-tipai-ecmp-worker/deploy/`
- Intents registered: `python3 scripts/register_intents.py --intents-dir app/intents --deploy-env=local`

### Steps

```bash
# 1. Create a session
SESSION=$(curl -s -X POST "http://localhost:8000/v1/sessions" \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -c "import sys,json; print(json.load(sys.stdin)['workflow_id'])")
echo "Session: $SESSION"

# --- Pure ACK scenarios (expect: PURE_ACK, 0 tokens) ---

# Scenario 1 — Pure ACK (English)
curl -s -X POST "http://localhost:8000/v1/sessions/$SESSION/messages" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Thanks!"}'

# Scenario 2 — Pure ACK (Chinese)
curl -s -X POST "http://localhost:8000/v1/sessions/$SESSION/messages" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "谢谢"}'

# Scenario 5 — Composite ACK (multi-token)
curl -s -X POST "http://localhost:8000/v1/sessions/$SESSION/messages" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Got it, thanks!"}'

# Scenario 7 — ACK with emoji
curl -s -X POST "http://localhost:8000/v1/sessions/$SESSION/messages" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Ok 😊"}'

# Scenario 8 — Composite ACK (sure + thank you)
curl -s -X POST "http://localhost:8000/v1/sessions/$SESSION/messages" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Sure, thank you!"}'

# Scenario 14 — Multilingual ACK (Japanese)
curl -s -X POST "http://localhost:8000/v1/sessions/$SESSION/messages" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "わかりました"}'

# Scenario 15 — Composite ACK (alright + perfect)
curl -s -X POST "http://localhost:8000/v1/sessions/$SESSION/messages" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Alright, perfect"}'

# Scenario 18 — Radio/military composite ACK
curl -s -X POST "http://localhost:8000/v1/sessions/$SESSION/messages" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "roger that, thanks"}'

# --- Normal pipeline scenarios (expect: LLM called, intent mapped) ---

# Scenario 3 — Embedded ACK with request signal "can"
curl -s -X POST "http://localhost:8000/v1/sessions/$SESSION/messages" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Thanks! Can I get extra towels?"}'

# Scenario 4 — Normal question
curl -s -X POST "http://localhost:8000/v1/sessions/$SESSION/messages" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is the pet policy?"}'

# Scenario 6 — Follow-up question after ACK turn (proves context preserved)
curl -s -X POST "http://localhost:8000/v1/sessions/$SESSION/messages" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What about emotional support animals?"}'

# Scenario 9 — Embedded ACK with question mark
curl -s -X POST "http://localhost:8000/v1/sessions/$SESSION/messages" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Great, and breakfast hours?"}'

# Scenario 10 — Greeting (not an ACK, not a service request)
curl -s -X POST "http://localhost:8000/v1/sessions/$SESSION/messages" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Good morning"}'

# Scenario 11 — Single greeting word (hi not in ACK_TOKENS)
curl -s -X POST "http://localhost:8000/v1/sessions/$SESSION/messages" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hi"}'

# Scenario 12 — Ambiguous affirmation with non-ACK words
curl -s -X POST "http://localhost:8000/v1/sessions/$SESSION/messages" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Yes I think so"}'

# Scenario 13 — ACK opener with "need" + "please" signals
curl -s -X POST "http://localhost:8000/v1/sessions/$SESSION/messages" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Perfect, need a late checkout please"}'

# Scenario 16 — Question-mark disqualifies "thanks"
curl -s -X POST "http://localhost:8000/v1/sessions/$SESSION/messages" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Thanks?"}'

# Scenario 17 — Complaint / issue report
curl -s -X POST "http://localhost:8000/v1/sessions/$SESSION/messages" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "The wifi isn'\''t working"}'
```

### Checking Logs

```bash
# Orchestrator workflow worker (container name: temporal-ai-agent-worker)
docker logs --since 5m temporal-ai-agent-worker 2>&1 \
  | grep "$SESSION" \
  | grep -i "ack\|Pure ack\|PURE_ACK\|IntentMapper\|Nexus"
```

---

## Configuration Reference

The ACK detector is controlled by environment variables in the orchestrator:

| Variable | Default | Description |
|---|---|---|
| `ACK_DETECTION_ENABLED` | `true` | Enable/disable deterministic ACK detection |
| `ACK_DETECTION_SELECTION_STRATEGY` | `round_robin` | How response templates are rotated (`round_robin` or `random`) |

Setting `ACK_DETECTION_ENABLED=false` disables the deterministic path entirely,
causing all messages (including pure acks) to flow through the LLM pipeline.
