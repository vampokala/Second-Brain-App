# TIP.AI Integration Guide

> How Chat/ECMP integrates with TIP.AI for guest message classification, RAG assessment, and response generation. Covers the current pipeline, what TIP.AI replaces, data contracts, and phasing.
>
> **Related docs:** [AI Workbench Guide](WORKBENCH-GUIDE.md) | [Architecture](ARCHITECTURE.md) | [API Routes](API-ROUTES.md)

---

## Table of Contents

1. [Overview](#1-overview)
2. [System Architecture](#2-system-architecture)
3. [Message Flow: Current vs Future](#3-message-flow-current-vs-future)
4. [Classification Pipeline Deep Dive](#4-classification-pipeline-deep-dive)
5. [RAG Assessment and Response Generation](#5-rag-assessment-and-response-generation)
6. [What We Send TIP.AI](#6-what-we-send-tipai)
7. [What TIP.AI Returns](#7-what-tipai-returns)
8. [Dashboard Data Contract](#8-dashboard-data-contract)
9. [Conversation State](#9-conversation-state)
10. [Taxonomy and Routing Reference](#10-taxonomy-and-routing-reference)
11. [Edge Cases and Test Suite](#11-edge-cases-and-test-suite)
12. [Configuration Constants](#12-configuration-constants)
13. [Phasing and Timeline](#13-phasing-and-timeline)
14. [Integration Checklist](#14-integration-checklist)

---

## 1. Overview

### Who Is Who

- **Chat/ECMP** (us) — The messaging platform. We receive guest messages via webhook, redact credit card numbers, route to the right handler, and power the analytics dashboard. (TIP.AI handles all other PII redaction on their side.)
- **TIP.AI** (them) — The AI platform. They classify guest intent, assess RAG answerability, and generate draft responses.

### Before / After

| Step | Today (ECMP Does Everything) | Tomorrow (TIP.AI Handles AI) |
|------|------------------------------|------------------------------|
| 1. Receive message | ECMP webhook, archive, evidence | Unchanged |
| 2. CC redaction | `has_payment_risk()` + `redact_cardish()` | ECMP redacts credit card numbers only; TIP.AI handles all other PII redaction |
| 3. Classification | 7-phase guard pipeline (`classify_messages_v3.9.py`, ~3900 lines) | TIP.AI classifies: `bucket_key`, `confidence`, `provenance` |
| 4. RAG assessment | Dashboard workbench (`llm.js` `buildSystemPrompt()`) | TIP.AI assesses: `answerability`, `response` |
| 5. Response generation | Dashboard LLM call (LiteLLM/Ollama) | TIP.AI generates personalized `response` |
| 6. Routing | ECMP router uses `bucket_key` + `confidence` | Unchanged logic, now using TIP.AI fields |

**Net effect:** Steps 3-5 collapse into a single `POST /v1/sessions/{id}/messages` call. ECMP sends a CC-redacted guest message and gets back classification + assessment + draft response synchronously. TIP.AI applies additional PII redaction on their end.

### Reference Files

| File | Purpose |
|------|---------|
| `classify_messages_v3.9.py` (~3900 lines) | Full 7-phase classification pipeline |
| `tipai_classification_profile_v2.md` | Pipeline summary, nuance handling, test cases |
| `v2/static/js/llm.js` | RAG assessment: `buildSystemPrompt()`, JSON schema |
| `v2/db.py` | DDL for all 16 PostgreSQL tables |
| `v2/models.py` | Pydantic models (`WorkbenchAssessmentCreate` ~50 fields) |
| `v2/routers/classification.py` | Import logic, `_VALID_METHODS`, column shift detection |

---

## 2. System Architecture

### End-to-End Flow

![Mermaid diagram 1](TIPAI-INTEGRATION_mermaid_assets/diagram-1.png)


### Session Model

| ECMP Concept | TIP.AI Equivalent |
|-------------|-------------------|
| `case_id` (conversation ID) | `session_id` (per-stay session) |
| `prev_bucket_key` (state tracking) | TIP.AI maintains internally via conversation history |
| `turn_count` (message index) | Derived from message sequence in session |
| New case = state reset | `POST /v1/sessions` creates a new session |
| Each message updates state | Automatic within `POST /v1/sessions/{id}/messages` |

### What Stays On Our Side

- Webhook ingestion and message archiving
- CC redaction only (we redact credit card numbers before sending; TIP.AI handles other PII)
- Routing decisions (bot vs human) based on TIP.AI response
- Dashboard analytics and visualization
- Human feedback collection and evaluation framework
- Product catalog and MARSHA mapping data

### What Moves to TIP.AI

- Intent classification (all 7 pipeline phases)
- RAG answerability assessment
- Draft response generation
- Conversation state tracking
- Brand voice application

---

## 3. Message Flow: Current vs Future

### Current Pipeline: 7-Phase Classification

![Mermaid diagram 2](TIPAI-INTEGRATION_mermaid_assets/diagram-2.png)


### Future: Single TIP.AI Call

![Mermaid diagram 3](TIPAI-INTEGRATION_mermaid_assets/diagram-3.png)


TIP.AI must replicate all 7 phases internally. The pipeline collapses from the caller's perspective, but the intelligence must be preserved.

---

## 4. Classification Pipeline Deep Dive

This section documents the classification intelligence TIP.AI must replicate. Each phase is described with its patterns, rules, and outputs.

### 4.1 Pre-Scan Flags

**Source:** `pre_scan()` at `classify_messages_v3.9.py` line 897

The pre-scan sets three boolean flags. It does **not** route — flags are consumed by later phases.

#### `is_safety_urgent`

| Pattern Type | Examples |
|-------------|---------|
| Multi-word phrases | "call 911", "medical emergency", "active shooter", "sexual assault", "human trafficking" |
| Single-word regex | `\b(911|ambulance|intruder|weapon|gun)\b` |
| Violence regex | `\b(assault(ed|ing)?|threat(en(ed|ing)?)?|attacked)\b` + proximity to victim words |
| Fire emergency | "there is a fire", "room is on fire", "fire alarm", "see flames" |
| Smoke emergency | "smoke alarm", "visible smoke", "smoke coming from" |
| Water emergency | "flooded"/"burst pipe" + room/bathroom context |

**Precision rules:**
- "smoke" alone is NOT a safety trigger — requires alarm/visibility context
- "knife" is filtered if near cutlery context ("fork", "spoon", "steak knife")
- "fire" alone is NOT a trigger — requires structural context ("room is on fire", "fire alarm")

#### `is_complaint_signal`

Set membership check against: `complaint`, `disappointed`, `unacceptable`, `terrible`, `worst`, `awful`, `disgusting`, `filthy`, `rude`, `unprofessional`, `never coming back`, `manager`, `supervisor`, `escalate`, `compensation`, `refund`, `overcharged`

#### `is_pure_ack`

Delegates to `is_pure_ack_or_greeting()` — see [Section 4.4](#44-pure-ack-detection).

### 4.2 Guards (Blocking)

Guards route immediately when triggered, bypassing all downstream phases.

#### Payment Guard

**Source:** `has_payment_risk()` at line 1307

| Check | Pattern | Output |
|-------|---------|--------|
| Payment keywords | `\b(card number|cvv|cvc|ccv|expiry|exp date|expiration|security code|ending in \d{4})\b` | `bucket_key=BILL_PROB_DISPUTE`, `method=PAYMENT_GUARD` |
| Card number | `\b(\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{1,7}|\d{13,19})\b` where stripped length >= 13, validated by Luhn | Same + redact digits |

#### Language Guard

**Source:** `is_non_english()` at line 1261

Counts alphabetic characters. If >=20% are non-Latin (outside Basic Latin 0x0041-007A, Latin-1 Supplement 0x00C0-024F, Latin Extended Additional 0x1E00-1EFF), routes to human.

**Exceptions (bypass language guard):**
- CJK acknowledgments: 好的, 谢谢, ありがとう, etc.
- CJK greetings: お世話になります, 您好, etc.
- Latin non-English acks: gracias, merci, danke, etc.

**Output:** `bucket_key=GENERAL_UNCLEAR`, `method=LANG_GUARD_NONLATIN`

### 4.3 Deterministic Routing

**Source:** `deterministic_pre_route()` at line 1369

Priority order — first match wins, result is LOCKED (skips LLM):

| Priority | Source | Method | Examples |
|----------|--------|--------|----------|
| 1 | Safety keywords (if `is_safety_urgent` flag set) | `DETERMINISTIC_SAFETY` | "call 911", "active shooter" |
| 2 | App button exact match (`APP_BUTTON_MAP`, 20+ entries, multilingual) | `DET_APP_BUTTON` | "towels", "退房", "タオル" |
| 3 | Typed request exact match (`TYPED_REQUEST_MAP`, 30+ entries) | `DET_TYPED_EXACT` | "check out", "late checkout", "wake-up call" |
| 4 | Polite noise exact match (`POLITE_NOISE_SET`) | `DET_POLITE_NOISE` | "great thanks", "namaste", "mahalo" |
| 5 | Regex routing table (12 compiled patterns) | `DET_REGEX` | "can I upgrade", "AC not working", "pool hours" |

**Regex routing table:**

| Pattern | Bucket | Description |
|---------|--------|-------------|
| `UPGRADE_REQUEST_RE` | ROOM_REQ_UPGRADE | "can I upgrade", "apply my SNA" |
| `ROOM_PREFERENCE_RE` | ROOM_REQ_PREFERENCE | "high floor", "ocean view" |
| `BELLBOY_LUGGAGE_RE` | ARR_REQ_LUGGAGE | "bellboy", "bring bags to room" |
| `CANCEL_MODIFY_RE` | RES_REQ_MODIFY_DATES | "cancel reservation", "change booking" |
| `CHILD_BREAKFAST_RE` | FNB_INFO_HOURS | "kids breakfast", "children meal" |
| `HVAC_REQUEST_RE` | MAINT_REQ_GENERAL | "AC not working", "too cold" |
| `SHUTTLE_AIRPORT_RE` | TRANS_INFO_SHUTTLE | "shuttle to airport" |
| `RESTAURANT_RESERVATION_RE` | FNB_REQ_RESERVATION | "table for 4" (must have dining context) |
| `TRAY_REMOVAL_RE` | FNB_REQ_ROOMSERVICE | "pick up plates", "remove tray" |
| `SHUTTLE_TIME_QUERY_RE` | TRANS_INFO_SHUTTLE | "what time shuttle" |
| `POOL_GYM_TIME_QUERY_RE` | AMEN_INFO_POOL_GYM | "pool hours", "gym open" |
| `FNB_TIME_QUERY_RE` | FNB_INFO_HOURS | "breakfast hours", "restaurant time" |

### 4.4 Pure Ack Detection

**Source:** `is_pure_ack_or_greeting()` at line 860

**Algorithm (order matters):**

1. Check CJK greetings — お世話になります, 您好, etc. -> ACK
2. Check Latin non-English acks — gracias, merci, danke, etc. -> ACK
3. Check CJK acks — 好的, 谢谢, ありがとう, etc. -> ACK
4. Check full phrase match against `PURE_ACK_PHRASES` (20 phrases) -> ACK
5. **REQUEST_SIGNALS check** — if ANY word is in `{can, could, please, need, want, request, when, what, where, how, is, are, do, does}` OR message contains `?` -> **NOT ACK** (critical disqualifier)
6. Single word -> check against `PURE_ACK_TOKENS` (40+ tokens)
7. 2-6 words -> all words must be in `PURE_ACK_TOKENS + PURE_ACK_FILLERS`, at least one ack token

**Embedded ack examples:**

| Message | Result | Why |
|---------|--------|-----|
| "Thanks!" | GENERAL_ACK | No request signal |
| "Thanks! Can I get towels?" | HK_REQ_SUPPLIES | "can" is a request signal |
| "Perfect, breakfast hours?" | FNB_INFO_HOURS | "?" is a request signal |
| "Got it, also need towels" | HK_REQ_SUPPLIES | "need" is a request signal |

### 4.5 Followup Inference

**Source:** `check_deterministic_followup()` at line 1539

Buckets declare their `followup_mode` in taxonomy. Code overrides also exist:

```
FOLLOWUP_MODE_OVERRIDES:
  QTY: {HK_REQ_SUPPLIES, HK_REQ_BEDDING}
  TIME: {DEP_REQ_LATE_CHECKOUT}
```

#### Numeric-Only Messages

When the message is purely numeric (`^\s*\d+\s*$`):
- If `prev_bucket_key` is in TIME set and number is 0-23 -> inherit prev bucket, `method=DETERMINISTIC_TIME`
- If `prev_bucket_key` is in QTY set and number is 1-20 -> inherit prev bucket, `method=DETERMINISTIC_QTY`

#### Time Formats

| Format | Example | Parsed |
|--------|---------|--------|
| `^\d{4}$` | "1300" | 13:00 |
| `^\d{1,2}:\d{2}(am|pm)?$` | "1:30pm" | 13:30 |
| `^\d{1,2}(am|pm)$` | "2pm" | 14:00 |

#### Quantity Formats

Pattern: `^\s*(\d+)\s*(please|pls|more|of them|of those)?\s*$`
Valid range: 1-20

#### Same/Ditto Patterns

| Pattern | Match Type | Method |
|---------|-----------|--------|
| `^\s*(same|ditto|same thing|another one|one more)\s*$` | Strict | `DETERMINISTIC_SAME` |
| `\b(same|same thing|same request|ditto)\b` in <15 words | Loose (extracts room numbers) | `DETERMINISTIC_SAME_LOOSE` |

### 4.6 LLM Classification (Fallback)

**Source:** `classify_with_llm()` at line 1766

When no deterministic rule matches, the message falls through to LLM classification.

**Prompt structure:**
- Full taxonomy (132 bucket_keys with short labels) passed as enum constraint
- Tool-use forcing: `classify_message` tool with JSON schema
- Context injection: `[Context: Previous message was {prev_bucket_key} in {prev_category}]`
- Dynamic rules blocks conditionally included based on allowed bucket_keys

**Key dynamic rules:**

| Rule | Purpose |
|------|---------|
| SHORT/AMBIGUOUS MESSAGES | Names, numbers, single words, <5 words with no intent -> GENERAL_UNCLEAR |
| CHECKOUT DISAMBIGUATION | Late checkout vs checkout notify vs checkout time inquiry |
| ROOM_REQ_ACCESSIBLE | ONLY for explicit wheelchair/ADA/handicap requests |
| SUPPLIES | Towels/toiletries/dental kits -> HK_REQ_SUPPLIES |
| MULTIPLE INTENTS | Most actionable wins (REQUEST > INFO) |

**LLM configuration:**

| Parameter | Value |
|-----------|-------|
| Model | Claude Sonnet 4.5 via LiteLLM |
| Temperature | 0 |
| Max output tokens | 1024 per message |
| Tool choice | Forced (`classify_message`) |

### 4.7 Post-Classification Guards

**Source:** Lines 2708-2719

After LLM classification, 4 sanity guards run. If a guard fails, the result is downgraded:

| Guard | Condition to Pass | Downgrade Method | Rationale |
|-------|-------------------|-----------------|-----------|
| FNB Reservation | Message contains `\b(restaurant|dinner|lunch|breakfast|table|bar|dining|pax|party of)\b` | `FNB_SANITY_DOWNGRADE` | LLM chose FNB_REQ_RESERVATION but no dining keywords present |
| Safety | `is_safety_urgent` pre-scan flag was set | `SAFETY_SANITY_DOWNGRADE` | LLM chose SAFETY_EMERG_SECURITY but no safety signals detected |
| Local Recommendations | Message contains `\b(recommend|suggestion|nearby|things to do|where should|best place)\b` | `LOCAL_SANITY_DOWNGRADE` | LLM chose GUEST_INFO_LOCAL but no recommendation signals |
| Loyalty Program | Message contains loyalty keywords AND contains `?` | `LOYAL_SANITY_DOWNGRADE` | LLM chose LOYAL_INFO_PROGRAM but no loyalty signals or not a question |

**Special case:** For the safety guard, if `is_pure_ack` or message length < 20 characters, downgrade to `GENERAL_ACK` instead of `GENERAL_UNCLEAR`.

---

## 5. RAG Assessment and Response Generation

### Current State

- **In `classify_messages_v3.9.py`:** RAG assessment is disabled (`ENABLE_RAG_ASSESSMENT = False`). The code exists but is not active in production.
- **In dashboard workbench (`llm.js`):** RAG assessment is live and used for evaluation and testing.

### `buildSystemPrompt()` Logic

**Source:** `v2/static/js/llm.js` line 142

The system prompt is constructed dynamically:

1. **Property data extraction** — `extractPropertyDataForBucket(marshaCode, bucketKey)` loads property data filtered by MARSHA mapping fields. `ALWAYS_CONTEXT_FIELDS` are always included:
   - `propertyBasicInfo.propertyName`
   - `propertyBasicInfo.city`, `.state`, `.country`
   - `propertyAdditionalInfo.brandName`

2. **Route mode determination** — `shouldGenerateDraft(bucketKey)` decides draft vs eval-only. RAG-eligible buckets get `routeMode=draft`; handoff buckets get `routeMode=eval-only`.

3. **Capabilities section** — `buildCapabilitiesSection()` lists what the AI can help with vs what needs a human, derived from taxonomy route types.

4. **Brand voice** — `getBrandVoicePrompt()` injects voice instructions and conversational fallback style.

5. **Conversation context** — If the message is ambiguous, prior messages are injected as a `PRIOR MESSAGES:` block.

### Assessment JSON Schema

The LLM returns a structured assessment:

```json
{
  "answerability": "FULL | PARTIAL | NONE",
  "confidence": "HIGH | MEDIUM | LOW",
  "interpreted_question": "<what guest is asking based on context>",
  "draft_response": "<response using ONLY property data>",
  "missing_data": "<what's missing, or null>",
  "clarifying_questions": "<questions for guest, or null>",
  "reasoning": "<brief explanation>",
  "none_reason": "topic_mismatch | data_missing | not_a_question | unclear | null",
  "detected_intents": ["<topic1>", "<topic2>"],
  "is_multi_intent": true | false,
  "bucket_seems_correct": true | false,
  "suggested_bucket": "<if bucket_seems_correct=false>"
}
```

`interpreted_question` only appears when conversation context is injected (ambiguous messages).

### Route-Specific Behavior

| Route Type | Draft Behavior | Assessment Behavior |
|-----------|---------------|-------------------|
| RAG-Only | Full auto-draft | FULL = send, PARTIAL = draft + flag, NONE = route to human |
| RAG+Human | Draft for associate review | Same assessment, draft is a suggestion |
| RAG+System | Draft may need system lookup | Assessment may return PARTIAL (needs PMS/API data) |
| Human-Full | Associate suggestion draft | Always generates a suggested response |
| Human-Light | Associate suggestion draft | Same as Human-Full |
| No-RAG | No draft | Route to human |

### NONE Reasons

| Reason | Meaning | Fix |
|--------|---------|-----|
| `topic_mismatch` | Wrong bucket assigned | Classification error |
| `data_missing` | Right bucket, no data | Enrich MARSHA catalog |
| `not_a_question` | Pure ack/statement | No response needed |
| `unclear` | Cannot determine intent | Ask clarifying question |

### What TIP.AI Returns Instead

TIP.AI returns the same schema, same fields. The difference is that classification, assessment, and response generation happen in a single API call rather than separate pipeline stages. The dashboard consumes TIP.AI output identically to how it consumes the current workbench output.

---

## 6. What We Send TIP.AI

### Per-Message Payload

Each guest message triggers a `POST /v1/sessions/{session_id}/messages` with:

- **Guest message** — CC-redacted text (card numbers masked, payment keywords flagged). TIP.AI applies additional PII redaction on their side.
- **Session context** — Established when the session was created; TIP.AI maintains conversation state internally
- **Role** — `CUSTOMER` for guest messages

### Property Data

Property data available in `prop_catalog` (keyed by MARSHA code):

- Basic info: property name, city, state, country, brand
- Amenities: pool hours, gym hours, spa services
- Policies: check-in/out times, pet policy, parking
- F&B: restaurant names, hours, room service menus
- Services: shuttle schedules, concierge offerings

### Configuration Data

| Data | Source | Purpose |
|------|--------|---------|
| Full taxonomy (132 buckets) | `taxonomy_data` table | Classification target set |
| MARSHA mapping | `marsha_mapping` table | Per-bucket property field mapping |
| Brand voice settings | Dashboard settings | Tone and persona for responses |
| Routing rules | `routing_rules` table | Manual overrides per bucket |

---

## 7. What TIP.AI Returns

### Classification Fields

| Field | Type | Description |
|-------|------|-------------|
| `bucket_key` | string | Classification result (e.g., `HK_REQ_SUPPLIES`) |
| `confidence` | float | Confidence score (mapped to HIGH/MEDIUM/LOW bands) |
| `provenance` | string | How classified (see provenance table below) |
| `reason_code` | string | Additional context (e.g., sanity guard name) |
| `category` | string | Top-level taxonomy category |
| `sub_query` | string[] | Detected sub-intents |

### Assessment Fields

| Field | Type | Description |
|-------|------|-------------|
| `answerability` | string | FULL, PARTIAL, or NONE |
| `response` | string | Draft response text |
| `rag.sources` | string[] | Source attribution |

### Telemetry

| Field | Type | Description |
|-------|------|-------------|
| `telemetry.tokens_used` | int | Token consumption |
| `telemetry.latency_ms` | int | Processing time |
| `model_version` | string | Model identifier |
| `taxonomy_version` | string | Taxonomy version used |

### Method Provenance Mapping

This table maps every `method` value from the current pipeline to TIP.AI's `provenance` values:

| Current ECMP Method | Meaning | TIP.AI Provenance | When Used |
|---------------------|---------|-------------------|-----------|
| `PAYMENT_GUARD` | Card number or payment keywords detected | `GUARD_PAYMENT` | CC in message |
| `LANG_GUARD_NONLATIN` | >=20% non-Latin characters | `GUARD_LANGUAGE` | Non-Latin script dominant |
| `DETERMINISTIC_SAFETY` | Safety pre-scan flag triggered | `DETERMINISTIC` | Emergency keywords |
| `DET_APP_BUTTON` | App button exact match | `DETERMINISTIC` | Mobile app button tap |
| `DET_APP_BUTTON_EXACT` | App button regex fullmatch | `DETERMINISTIC` | Variant of above |
| `DET_TYPED_EXACT` | Typed request exact match | `DETERMINISTIC` | High-frequency phrase |
| `DET_POLITE_NOISE` | Polite noise exact match | `DETERMINISTIC` | "great thanks", etc. |
| `DET_REGEX` | Regex routing table match | `DETERMINISTIC` | Pattern match |
| `PURE_ACK` | Pure acknowledgment detected | `DETERMINISTIC` | Thanks/ok/greeting |
| `DETERMINISTIC_QTY` | Numeric followup (quantity) | `DETERMINISTIC` | "3" after supplies |
| `DETERMINISTIC_TIME` | Numeric followup (time) | `DETERMINISTIC` | "11" after checkout |
| `DETERMINISTIC_SAME` | "Same"/"ditto" strict match | `DETERMINISTIC` | Repeat request |
| `DETERMINISTIC_SAME_LOOSE` | "Same" in short message with room | `DETERMINISTIC` | "Same for 102" |
| `LLM` | LLM classification | `LLM` | Fallback classification |
| `FNB_SANITY_DOWNGRADE` | Post-guard: no dining keywords | `LLM` + reason_code | Sanity check failed |
| `SAFETY_SANITY_DOWNGRADE` | Post-guard: no safety signals | `LLM` + reason_code | Sanity check failed |
| `LOCAL_SANITY_DOWNGRADE` | Post-guard: no recommendation signals | `LLM` + reason_code | Sanity check failed |
| `LOYAL_SANITY_DOWNGRADE` | Post-guard: no loyalty signals | `LLM` + reason_code | Sanity check failed |
| `LLM_ERROR` | LLM call failed | `ERROR` | API failure |
| `ERROR` | Processing error | `ERROR` | Exception |
| `SKIPPED` | Message skipped (agent role) | -- | Non-guest message |
| `CASE_QUARANTINED` | Entire case quarantined | -- | Context overflow |

---

## 8. Dashboard Data Contract

### 8.1 `classification_rows` Table

**DDL:** `v2/db.py` line 74

| Column | Type | TIP.AI Response Source |
|--------|------|----------------------|
| `id_case` | TEXT NOT NULL | `application_info.conversation_id` |
| `message_index` | INTEGER | Sequence within session |
| `message_role` | TEXT | `role` from request |
| `message_text` | TEXT | `prompt` from request |
| `bucket_key` | TEXT | `intent_mapping.intent_details[0].bucket_key` |
| `method` | TEXT | `intent_mapping.intent_details[0].provenance` |
| `confidence` | TEXT | Computed from `intent_details[0].confidence` float |
| `extra` | JSONB | Overflow fields (sentiment, reason_code, etc.) |

**Indexes:** `bucket_key`, `id_case`, `message_role`, `(message_role, bucket_key)` WHERE `role='CUSTOMER'`

**Unique constraint:** `(id_case, message_index)`

### 8.2 `workbench_assessments` Table (~50 columns)

**DDL:** `v2/db.py` line 141 | **Pydantic model:** `WorkbenchAssessmentCreate` at `v2/models.py` line 86

#### Core Assessment

| Column | Type | TIP.AI Source |
|--------|------|--------------|
| `answerability` | TEXT | `rag.answerability` |
| `confidence` | TEXT | Computed from `intent_details[].confidence` |
| `interpreted_question` | TEXT | Context-derived interpretation |
| `draft_response` | TEXT | `response` |
| `reasoning` | TEXT | Internal reasoning |
| `missing_data` | TEXT | What data is missing |
| `none_reason` | TEXT | Why NONE |
| `detected_intents` | JSONB | `intent_mapping.intent_details[].sub_query` |
| `is_multi_intent` | BOOLEAN | `len(intent_details) > 1` |
| `bucket_seems_correct` | BOOLEAN | Self-check |
| `suggested_bucket` | TEXT | Alternative if incorrect |
| `clarifying_questions` | JSONB | Questions for guest |

#### Context

| Column | Type | TIP.AI Source |
|--------|------|--------------|
| `property` | TEXT | `context.reservation.propertyCode` |
| `case_id` | TEXT | `application_info.conversation_id` |
| `message_index` | INTEGER | Turn number |
| `intent` | TEXT | `bucket_key` |
| `message` | TEXT | Guest message text |
| `ambiguous` | BOOLEAN | Whether context was needed |
| `conversation_context` | TEXT | Prior messages text |

#### Coverage

| Column | Type | TIP.AI Source |
|--------|------|--------------|
| `coverage_tier` | TEXT | From MARSHA mapping |
| `coverage_pct` | REAL | % of fields with data |
| `mapped_fields` | JSONB | `rag.sources` |
| `fields_found_count` | INTEGER | Fields with actual data |

#### Route

| Column | Type | TIP.AI Source |
|--------|------|--------------|
| `route_mode` | TEXT | "draft" or "eval-only" |
| `route` | TEXT | Taxonomy route type |
| `rag_mode` | TEXT | Taxonomy rag_mode |
| `route_override` | BOOLEAN | Manual override flag |

#### Human Feedback (populated by reviewers, not TIP.AI)

| Column | Type | Purpose |
|--------|------|---------|
| `fb_answerability` | TEXT | Reviewer's assessment |
| `fb_response` | TEXT | Reviewer's expected response |
| `fb_bucket` | TEXT | Reviewer's bucket choice |
| `fb_corrected_response` | TEXT | Edited draft |
| `fb_failure_reasons` | JSONB | What went wrong |
| `fb_hallucination_severity` | TEXT | Hallucination level |
| `fb_safe_to_send` | BOOLEAN | Send-worthy? |
| `fb_reviewer_id` | TEXT | Who reviewed |

#### Telemetry

| Column | Type | TIP.AI Source |
|--------|------|--------------|
| `response_time_ms` | INTEGER | `telemetry.latency_ms` |
| `response_length` | INTEGER | Length of `draft_response` |
| `input_tokens` | INTEGER | `telemetry.tokens_used` (input) |
| `output_tokens` | INTEGER | `telemetry.tokens_used` (output) |
| `model` | TEXT | `model_version` |
| `backend` | TEXT | `"tipai"` |
| `prompt_version` | TEXT | `taxonomy_version` |

### 8.3 Response Field Mapping (Rosetta Stone)

This table maps each TIP.AI response field to the dashboard table and column it populates:

| TIP.AI Response Field | Dashboard Table | Dashboard Column |
|----------------------|-----------------|-----------------|
| `intent_mapping.intent_details[0].bucket_key` | `classification_rows` | `bucket_key` |
| `intent_mapping.intent_details[0].confidence` | `classification_rows` | `confidence` |
| `intent_mapping.intent_details[0].provenance` | `classification_rows` | `method` |
| `intent_mapping.intent_details[0].reason_code` | `classification_rows` | `extra->reason` |
| `intent_mapping.intent_details[0].category` | `workbench_assessments` | `taxonomy_category` |
| `intent_mapping.intent_details[0].sub_query` | `workbench_assessments` | `detected_intents` |
| `intent_mapping.intent_details` (length) | `workbench_assessments` | `is_multi_intent` |
| `response` | `workbench_assessments` | `draft_response` |
| `rag.answerability` | `workbench_assessments` | `answerability` |
| `rag.sources` | `workbench_assessments` | `mapped_fields` |
| `sentiment` | `classification_rows` | `extra->sentiment` |
| `telemetry.tokens_used` | `workbench_assessments` | `input_tokens` + `output_tokens` |
| `telemetry.latency_ms` | `workbench_assessments` | `response_time_ms` |
| `model_version` | `workbench_assessments` | `model` |
| `taxonomy_version` | `workbench_assessments` | `prompt_version` |
| `application_info.conversation_id` | `classification_rows` | `id_case` |

### 8.4 Import Endpoints

| Endpoint | Method | Purpose | Pydantic Model |
|----------|--------|---------|---------------|
| `/api/classification/bulk` | POST | Upsert classification rows | `ClassificationBulkImport` |
| `/api/classification/import-csv` | POST | Import classification CSV | Multipart file |
| `/api/workbench/assessments` | POST | Save single assessment | `WorkbenchAssessmentCreate` |
| `/api/workbench/assessments/bulk` | POST | Bulk import assessments | `WorkbenchBulkImport` |
| `/api/taxonomy/bulk` | POST | Upsert taxonomy data | `TaxonomyBulkImport` |

---

## 9. Conversation State

### State Fields

The current pipeline tracks per-conversation state:

| Field | Type | Purpose |
|-------|------|---------|
| `prev_bucket_key` | string | Last non-ACK, non-ERROR bucket |
| `prev_category` | string | Category of `prev_bucket_key` |
| `prev_item` | string | Extracted item (room number, quantity, time) |
| `turn_count` | int | Message index within case |

### ACK Rule

ACKs do not update conversation state:

```
if result.bucket_key
   AND "ERROR" not in result.method
   AND result.bucket_key != "GENERAL_ACK":
    update state with new bucket
```

This ensures followup inference works correctly across ack interruptions.

### Multi-Turn Flow Example

![Mermaid diagram 4](TIPAI-INTEGRATION_mermaid_assets/diagram-4.png)


### TIP.AI Session Mapping

| ECMP Pipeline State | TIP.AI Session Equivalent |
|--------------------|-----------------------------|
| `ConversationContext.case_id` | `session_id` (per-stay session) |
| `prev_bucket_key` | TIP.AI maintains internally via conversation history |
| `turn_count` | Derived from message sequence in session |
| State reset on new case | Session creation (`POST /v1/sessions`) |
| State update on each message | Automatic within `POST /v1/sessions/{id}/messages` |

---

## 10. Taxonomy and Routing Reference

### Bucket Naming Convention

Pattern: `PREFIX_TYPE_TOPIC`

| Prefix | Domain |
|--------|--------|
| `HK_` | Housekeeping |
| `FNB_` | Food & Beverage |
| `ARR_` | Arrival |
| `DEP_` | Departure |
| `ROOM_` | Room |
| `RES_` | Reservation |
| `TRANS_` | Transportation |
| `AMEN_` | Amenities |
| `MAINT_` | Maintenance |
| `SAFETY_` | Safety/Emergency |
| `LOYAL_` | Loyalty |
| `DIGITAL_` | Digital/Mobile |
| `FIN_` | Financial |
| `GUEST_` | Guest Services |
| `GEN_` | General |
| `GENERAL_` | System-level (ACK, UNCLEAR, OOS) |

| Type Infix | Meaning |
|-----------|---------|
| `_REQ_` | Request |
| `_INFO_` | Information query |
| `_PROB_` | Problem/complaint |
| `_EMERG_` | Emergency |

### Route Types

| Route | Description | Draft Behavior |
|-------|-------------|---------------|
| RAG-Only | Fully automatable from property data | Auto-draft, deflection candidate |
| RAG+Human | Automatable but needs human review | Draft for associate approval |
| RAG+System | Needs PMS/API lookup | Draft partial, flag for system action |
| Human-Full | Complex, requires human judgment | Suggested response only |
| Human-Light | Simple handoff to associate | Suggested response only |
| No-RAG | Cannot be automated | Route to human, no draft |

### How Routing Decisions Are Made

![Mermaid diagram 5](TIPAI-INTEGRATION_mermaid_assets/diagram-5.png)


| Priority | Source | Mechanism |
|----------|--------|-----------|
| 1 (highest) | Manual override | `routingRules[bucket].action` set in Config modal |
| 2 | Taxonomy default | `taxonomyLookup[bucket].route` / `.rag_mode` from CSV import |
| 3 (fallback) | No taxonomy match | Defaults to BOT (generate draft) |

---

## 11. Edge Cases and Test Suite

These are the cases TIP.AI must handle correctly. They represent the precision requirements of the classification pipeline.

### 11.1 Embedded Acks

REQUEST_SIGNALS `{can, could, please, need, want, request, when, what, where, how, is, are, do, does}` plus `?` disqualify pure ack classification.

| Message | Expected | Why |
|---------|----------|-----|
| "Thanks!" | GENERAL_ACK | No request signal |
| "Thanks! Need towels" | HK_REQ_SUPPLIES | "need" is request signal |
| "Perfect, breakfast hours?" | FNB_INFO_HOURS | "?" is request signal |
| "Great, can I also get pillows?" | HK_REQ_BEDDING | "can" is request signal |
| "Ok thanks" | GENERAL_ACK | No request signal |
| "Understood, what time is checkout?" | ARR_INFO_CHECKOUT | "what" + "?" |
| "好的谢谢" | GENERAL_ACK | CJK ack |
| "Gracias" | GENERAL_ACK | Latin non-English ack |

### 11.2 Fragment/Followup Handling

| Prev Bucket | Message | Expected | Method |
|------------|---------|----------|--------|
| HK_REQ_SUPPLIES | "3" | HK_REQ_SUPPLIES (Qty: 3) | DETERMINISTIC_QTY |
| HK_REQ_SUPPLIES | "3 please" | HK_REQ_SUPPLIES (Qty: 3) | DETERMINISTIC_QTY |
| DEP_REQ_LATE_CHECKOUT | "11" | DEP_REQ_LATE_CHECKOUT (Time: 11:00) | DETERMINISTIC_TIME |
| DEP_REQ_LATE_CHECKOUT | "1:30pm" | DEP_REQ_LATE_CHECKOUT (Time: 13:30) | DETERMINISTIC_TIME |
| DEP_REQ_LATE_CHECKOUT | "1300" | DEP_REQ_LATE_CHECKOUT (Time: 13:00) | DETERMINISTIC_TIME |
| HK_REQ_SUPPLIES | "same" | HK_REQ_SUPPLIES (Same) | DETERMINISTIC_SAME |
| HK_REQ_SUPPLIES | "Same for room 102" | HK_REQ_SUPPLIES (Same, Room: 102) | DETERMINISTIC_SAME_LOOSE |
| HK_REQ_SUPPLIES | "25" | Falls through (QTY_MAX is 20) | LLM |
| AMEN_INFO_POOL | "3" | Falls through (no followup_mode) | LLM |

### 11.3 Checkout Disambiguation

| Message | Expected Bucket | Why |
|---------|----------------|-----|
| "Checking out tomorrow" | DEP_REQ_CHECKOUT_NOTIFY | Statement (notification) |
| "Late checkout please" | DEP_REQ_LATE_CHECKOUT | Request with "please" |
| "Checkout at 1pm" | DEP_REQ_LATE_CHECKOUT | Time specified = late request |
| "What time is checkout?" | ARR_INFO_CHECKOUT | Question about policy |

### 11.4 Safety Precision

| Message | Expected Bucket | Why |
|---------|----------------|-----|
| "Smoke in my room!" | SAFETY_EMERG_SECURITY | Smoke + room context |
| "Room smells like smoke" | MAINT_PROB_SMELL | Odor complaint, not fire |
| "Call 911" | SAFETY_EMERG_SECURITY | Explicit emergency phrase |
| "Fire alarm going off" | SAFETY_EMERG_SECURITY | SMOKE_EMERG_RE matches |
| "See flames in hallway" | SAFETY_EMERG_SECURITY | FIRE_EMERG_RE matches |
| "This is an emergency" | LLM fallback | No specific safety phrases |
| "Knife missing from room service" | NOT safety | Benign knife context (cutlery) |

### 11.5 Sanity Guard Examples

| Message | LLM Chose | Guard | Expected After Guard |
|---------|-----------|-------|---------------------|
| "Thanks for everything!" | SAFETY_EMERG_SECURITY | Safety fails (no flag, is_pure_ack) | GENERAL_ACK |
| "Hi" | SAFETY_EMERG_SECURITY | Safety fails (no flag, len < 20) | GENERAL_ACK |
| "Room 304" | SAFETY_EMERG_SECURITY | Safety fails | GENERAL_UNCLEAR |
| "Can you help?" | FNB_REQ_RESERVATION | FNB fails (no dining keywords) | GENERAL_UNCLEAR |
| "Dinner reservation for 4" | FNB_REQ_RESERVATION | FNB passes ("dinner") | FNB_REQ_RESERVATION |
| "Any restaurant recommendations?" | GUEST_INFO_LOCAL | Local passes ("recommendations") | GUEST_INFO_LOCAL |
| "What are my elite benefits?" | LOYAL_INFO_PROGRAM | Loyalty passes ("elite", "benefits", "?") | LOYAL_INFO_PROGRAM |
| "Thank you for the upgrade" | LOYAL_INFO_PROGRAM | Loyalty fails (no "?") | GENERAL_UNCLEAR |

### 11.6 Guard Test Cases

| Message | Expected | Method |
|---------|----------|--------|
| "4111 1111 1111 1111" | BILL_PROB_DISPUTE | PAYMENT_GUARD |
| "这是我的房间号码" | GENERAL_UNCLEAR | LANG_GUARD_NONLATIN |
| "好的" | GENERAL_ACK | CJK ack bypasses lang guard |

---

## 12. Configuration Constants

All tunable parameters from the current pipeline in one reference table:

| Parameter | Value | Notes |
|-----------|-------|-------|
| `QTY_MIN` | 1 | Minimum valid quantity |
| `QTY_MAX` | 20 | Maximum valid quantity |
| `TIME_HOUR_MAX` | 23 | Maximum valid hour |
| Non-Latin threshold | 20% | `(non_latin / letters) >= 0.20` |
| Short message threshold | <=2 words or <15 chars | For GENERAL_UNCLEAR |
| LLM temperature | 0 | Deterministic output |
| Max output tokens | 1024 | Per-message LLM budget |
| Rate limit | 2000 RPM | LiteLLM rate limiting |
| Max retries | 5 | Exponential backoff |
| Message truncation | 500 chars | Input to LLM |
| `ALWAYS_CONTEXT_FIELDS` | 5 fields | Always included in RAG |
| Card number min length | 13 digits | Payment guard threshold |
| Pure ack max words | 6 | Token analysis limit |
| Request signal set size | 14 words | Ack disqualifiers |

---

## 13. Phasing and Timeline

### Phase 1: Shadow Mode (Q1-Q2 2026)

TIP.AI runs in parallel with the existing pipeline. All output is logged but not surfaced to associates or guests.

| Component | Status |
|-----------|--------|
| Classification | Required |
| RAG Assessment | Required |
| Draft Response | Required (logged only) |
| Sentiment | Required |
| Stay Events | Optional |

### Phase 2: Associate Preview (Q2-Q3 2026)

TIP.AI responses are surfaced to associates as suggestions. Associates can use, edit, or ignore them.

| Component | Status |
|-----------|--------|
| Classification | Required |
| RAG Assessment | Required (gating) |
| Draft Response | Required (surfaced to associate) |
| Sentiment | Required |
| Stay Events | Required |

### Phase 3: Deflection (Q3+ 2026)

For RAG-eligible buckets with FULL answerability, responses are auto-sent to guests without associate intervention.

| Component | Status |
|-----------|--------|
| Classification | Required |
| RAG Assessment | Required (auto-send gating) |
| Draft Response | Required (auto-send for FULL) |
| Sentiment | Required |
| Stay Events | Required |

### Latency Budget

For TIP.AI to meet P95 < 2000ms:

| Stage | Target |
|-------|--------|
| Deterministic classification | < 10ms |
| LLM classification | < 1000ms |
| RAG lookup + assessment | < 500ms |
| Draft generation | Can overlap with assessment |
| **Total** | **< 2000ms** |

---

## 14. Integration Checklist

### TIP.AI Must Implement

**Classification:**
- [ ] Pre-scan flags (safety, complaint, ack) before routing
- [ ] Payment guard (Luhn validation, keyword detection)
- [ ] Language guard (non-Latin threshold with CJK exceptions)
- [ ] Deterministic routing with priority (exact match > regex > LLM)
- [ ] Request signal detection (disqualifies pure ack)
- [ ] Followup mode per bucket (QTY vs TIME)
- [ ] Same/ditto pattern matching
- [ ] LLM fallback classification with full taxonomy
- [ ] Post-classification sanity guards (FNB, safety, local, loyalty)
- [ ] Conversation state tracking (`prev_bucket_key` not updated by ACKs)

**Assessment:**
- [ ] RAG answerability assessment (FULL / PARTIAL / NONE)
- [ ] Property data extraction via MARSHA mapping
- [ ] Ambiguity detection and context injection
- [ ] Capabilities section generation from taxonomy

**Response:**
- [ ] Draft response generation with brand voice
- [ ] Route-specific behavior (auto-draft vs suggestion)
- [ ] Language matching (respond in guest's language)

**Output:**
- [ ] Return all fields in the Rosetta Stone mapping table (Section 8.3)
- [ ] Provenance values matching the mapping table (Section 7)
- [ ] Confidence as float (dashboard converts to HIGH/MEDIUM/LOW)
- [ ] Telemetry fields (tokens, latency)

### Dashboard Must Build/Change

- [ ] TIP.AI API client (replace LLM direct calls with TIP.AI endpoint)
- [ ] Response adapter (map TIP.AI JSON to `ClassificationRow` and `WorkbenchAssessmentCreate`)
- [ ] Shadow mode toggle (Phase 1: log only, no routing changes)
- [ ] Side-by-side comparison view (current pipeline vs TIP.AI during shadow)
- [ ] `backend` field support (distinguish "tipai" from "litellm"/"ollama" in assessments)
- [ ] Sentiment storage (new field in `classification_rows.extra` JSONB)

---

*TIP.AI Integration Guide v1.0 | 2026-03-23 | ECMP Engineering (AI Dashboard Team)*
