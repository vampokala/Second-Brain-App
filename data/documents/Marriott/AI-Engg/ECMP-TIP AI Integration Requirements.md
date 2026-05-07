# ECMP × TIP.AI Integration Requirements 

|Field           |Value                                                        | 

|----------------|-------------------------------------------------------------| 

|**Document**    |ECMP-TIPAI-INT-002                                           | 

|**Version**     |3.0                                                          | 

|**Author**      |Rami — Senior Director, Engineering & Architecture           | 

|**Organization**|ECMP / Operations Systems Development (OSD)                  | 

|**Audience**    |Paul + TIP.AI Engineering, Greg, Rich DiStefano, Arun Menavan| 

|**Date**        |February 2026                                                | 

|**Status**      |Draft — Open Questions Inline                                | 

----- 

## Purpose 

This document defines the integration requirements between ECMP (Enterprise Chat Messaging Platform) and TIP.AI for guest messaging classification, response generation, and conversational intelligence. 

It specifies: what ECMP sends, what ECMP expects back, what artifacts ECMP delivers, and the non-functional requirements TIP.AI must meet. It does not prescribe TIP.AI’s internal architecture, data sourcing, prompt engineering, or implementation approach. 

This is the single integration specification. Everything Paul’s team needs to evaluate and build against is contained here. 

----- 

## Key Design Decisions 

These decisions are final and inform every section of this document. 

1. **ECMP extends the existing TIP.AI session-based API** — `POST /v1/sessions`, `POST /v1/sessions/{id}/messages`, new `PATCH /v1/sessions/{id}`. No new architectural patterns. 

2. **Everything is synchronous** — classification, draft generation, sentiment, and RAG answerability are returned in a single HTTP response. 

3. **ECMP does not classify messages.** ECMP redacts PII/CC and sends every guest message to TIP.AI. TIP.AI owns all classification — bucket_key, confidence, sentiment, RAG assessment, and draft generation. 

4. **Structured context replaces prompt blobs.** ECMP sends structured JSON context at session creation (guest, reservation, stay events). TIP.AI owns prompt assembly, RAG data sourcing, and guardrail enforcement internally. There is no `aggregator_system_prompt` in this contract. 

5. **ECMP provides brand voice and intent taxonomy as versioned artifacts.** Delivery mechanism (registry, API, file sync) to be agreed with TIP.AI engineering. TIP.AI hosts and consumes them however makes sense for their architecture. 

6. **Single TIP.AI session per guest per stay.** ECMP internally models conversations as guest + stay + channel (one conversation per channel). However, TIP.AI maintains a single session per guest per stay, with `channel` specified per-message. This means TIP.AI has unified cross-channel conversation context — if a guest asks about EV charging on SMS and later opens the Bonvoy app, TIP.AI knows the prior exchange. ECMP maps its internal per-channel conversations to the single TIP.AI session. This is a deliberate decoupling: ECMP’s conversation boundary is a delivery/routing concern; TIP.AI’s session boundary is an intelligence/context concern. 

7. **TIP.AI processes associate messages for conversation state.** When ECMP sends associate messages (`role: associate`), TIP.AI records them to conversation history, tracks intent resolution, and extracts stay-relevant events such as commitments, promises, and service actions (e.g., “I’ll reserve a spot near the chargers” → stay event). Extracted events are returned in the response so ECMP can persist them. This is a new capability — see Phasing for rollout expectations. 

----- 

## What Exists Today 

Session-based API (`POST /v1/sessions` to create, `POST /v1/sessions/{id}/messages` to interact). Synchronous HTTP via rest-sync mode. Shadow mode flag. Intent mapping with labels and multi-intent decomposition. Slot filling for followup. `application_info` pass-through for ECMP metadata. Response text returned. `description` field for prompt context. Already handles policy QA and hotel search intents. 

## What ECMP Needs Added 

Fine-grained classification (`bucket_key` mapped to ECMP’s hospitality intent taxonomy), per-intent confidence scoring, per-message sentiment, RAG answerability assessment, role-aware message handling, channel-aware drafting, structured context consumption, session patching, `program` identifier for conversation origination, stay event tracking, and brand voice configuration consumption. 

----- 

## Interaction Flows 

All flows use the same TIP.AI session endpoints. The difference is who initiates and why. 

### Flow 1: Pre-Arrival (Session Initialization) 

ECMP scheduler triggers on reservation events within the pre-arrival window. This flow creates the TIP.AI session — no message is posted yet. 

|ECMP (Exists)                                            |TIP.AI (Existing Endpoint)                                                    |Notes                                  | 

|---------------------------------------------------------|------------------------------------------------------------------------------|---------------------------------------| 

|Scheduler fires on reservation event                     |`POST /v1/sessions`                                                           |Creates session with structured context| 

|Consent check → archive → evidence                       |Returns `session_id` + status                                                 |Session is now ready for messages      | 

|Sends structured context: guest, reservation, stay events|TIP.AI loads context, resolves brand voice + taxonomy from versioned artifacts|No message classification at this stage| 

|Sets `program: "pre-arrival"`                            |TIP.AI records origination context                                            |Used for analytics and behavior tuning | 

The first `POST /v1/sessions/{id}/messages` occurs when the guest replies to the pre-arrival SMS. Until then, the session exists but has no message history. 

### Flow 2: Guest Inbound (Guest → Associate) 

Guest replies to a message or initiates a new conversation. This is where classification matters most. 

|ECMP Pipeline (Exists)                       |TIP.AI (Existing Endpoint + Extensions)                              |ECMP Routing (Exists)        | 

|---------------------------------------------|---------------------------------------------------------------------|-----------------------------| 

|Webhook API → archive → evidence             |`POST /v1/sessions/{id}/messages`                                    |Router acts on classification| 

|PII/CC redaction **(TO BUILD)**              |Classify intent → return `bucket_key` from ECMP taxonomy **(EXTEND)**|GxP Adapter → associate view | 

|STOP/START → Consent Service                 |Per-intent confidence **(NEW)**                                      |TIP AI Adapter → telemetry   | 

|Reuse existing TIP.AI session for this stay  |Sentiment **(NEW)**                                                  |Evidence update              | 

|Post message with `role: guest` and `channel`|RAG answerability **(NEW)**                                          |                             | 

|                                             |`response` text = personalized draft                                 |                             | 

|                                             |Conversation history maintained within session                       |                             | 

### Flow 3: Associate Outbound (Associate → Guest) 

Associate responds via GxP. TIP.AI sees the outbound message to track intent resolution and maintain conversation state. 

|ECMP Pipeline (Exists)                       |TIP.AI (Existing Endpoint)                                                         |ECMP Delivery (Exists)              | 

|---------------------------------------------|-----------------------------------------------------------------------------------|------------------------------------| 

|GxP fires outbound message event             |`POST /v1/sessions/{id}/messages` with `role: associate`                           |Template render + send via Syniverse| 

|Archive → evidence → consent check           |No classification, no draft — role gates behavior                                  |DLR tracking                        | 

|Post associate message with `role: associate`|Record message to conversation history                                             |Evidence update                     | 

|                                             |Track intents, close resolved intents                                              |                                    | 

|                                             |Extract stay events (commitments, service actions) and return in response **(NEW)**|                                    | 

----- 

## Session Model 

ECMP creates one TIP.AI session per guest per stay. At session creation, ECMP sends structured context containing everything TIP.AI needs to personalize the conversation. 

**Session lifecycle:** 

- **Created** when the reservation event fires (pre-arrival) or when the first guest message arrives (walk-in, no pre-arrival trigger) 

- **Active** for the duration of the stay 

- **Patched** when stay context changes mid-stay (room upgrades, late checkout, service recovery, new stay events) 

- **Closed** at checkout or stay expiration 

**Session keying:** Sessions are keyed to reservation confirmation number. Edge cases (walk-ins without reservations, overlapping stays, group bookings) are handled by ECMP routing logic and do not affect the TIP.AI contract. 

**Cross-channel context:** Because the session is per-stay (not per-channel), TIP.AI maintains unified conversation history across SMS, app chat, and future channels. ECMP sends `channel` on every message so TIP.AI can adapt draft formatting. ECMP maps its internal per-channel conversations to the single TIP.AI session. 

> **Design note for ECMP spec:** This decoupling — ECMP conversations are per-channel, TIP.AI sessions are per-stay — must be reflected in the ECMP general design specification. ECMP’s TIP.AI Adapter is responsible for the mapping: multiple ECMP `conversation_id` values can reference the same TIP.AI `session_id`. 

### Personalization Requirement 

Personalization is a design requirement, not just a data field. ECMP provides guest identity, reservation details, and brand voice configuration. TIP.AI’s response generation must actively use this context in every draft. 

Draft responses must address the guest by name, reflect their Bonvoy tier (a Titanium Elite member receives different language than a first-time guest), reference the specific property and its amenities, use actual reservation details rather than generic Marriott defaults, and respond in the guest’s preferred language when available. 

How TIP.AI achieves this — prompt engineering, context injection, fine-tuning, or other techniques — is an engineering decision for Paul’s team. The requirement is that the output is personalized. 

----- 

## Request Contract 

### Session Creation — `POST /v1/sessions` 

|Status    |Field                |Description                                                                                                                                                                                                                                 | 

|----------|---------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------| 

|**EXISTS**|(endpoint)           |No endpoint change needed                                                                                                                                                                                                                   | 

|**NEW**   |`program`            |Conversation origination identifier: `pre-arrival`, `service-recovery`, `walk-in`, etc. TIP.AI records for analytics and can use to tune behavior. Avoids re-tokenizing the same context on repeated messages since not every guest replies.| 

|**NEW**   |`brand_code`         |Brand identifier (e.g., `marriott`, `westin`, `courtyard`). TIP.AI resolves brand voice configuration from its artifact store.                                                                                                              | 

|**NEW**   |`brand_voice_version`|Pins to a specific brand voice configuration release.                                                                                                                                                                                       | 

|**NEW**   |`taxonomy_version`   |Pins classification to a specific taxonomy release.                                                                                                                                                                                         | 

|**NEW**   |`context.guest`      |Guest identity: `guest_id`, `firstName`, `lastName`, `bonvoyTier`, `language`, `preferences`                                                                                                                                                | 

|**NEW**   |`context.reservation`|Reservation details: `confirmationNumber`, `propertyCode`, `arrivalDate`, `departureDate`, `roomType`, `specialRequests`                                                                                                                    | 

|**NEW**   |`context.stay_events`|Initial stay events (usually empty at creation). Structured, appendable array.                                                                                                                                                              | 

|**EXISTS**|`application_info`   |Pass-through for ECMP correlation: `conversation_id`. No change.                                                                                                                                                                            | 

**Example:** 

```json 

{ 

  "program": "pre-arrival", 

  "brand_code": "marriott", 

  "brand_voice_version": "2026-02-01", 

  "taxonomy_version": "2026-02-01", 

  "context": { 

    "guest": { 

      "guest_id": "G-88234", 

      "firstName": "Sarah", 

      "lastName": "Chen", 

      "bonvoyTier": "TITANIUM_ELITE", 

      "language": "en", 

      "preferences": ["feather-free pillows"] 

    }, 

    "reservation": { 

      "confirmationNumber": "R8834521", 

      "propertyCode": "MIA01", 

      "arrivalDate": "2026-02-15", 

      "departureDate": "2026-02-18", 

      "roomType": "King Suite", 

      "specialRequests": ["High floor", "late checkout if available"] 

    }, 

    "stay_events": [] 

  }, 

  "application_info": { 

    "conversation_id": "3b2f9e71-9d9b-47f4-9b2e-3dbd3a7f6a0b" 

  } 

} 

``` 

**Response:** 

```json 

{ 

  "session_id": "sess_01JKQM8X7N...", 

  "status": "active" 

} 

``` 

### Per-Message — `POST /v1/sessions/{id}/messages` 

|Status    |Field             |Description                                                                                                                                                          | 

|----------|------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------| 

|**EXISTS**|`prompt`          |Message text (PII-redacted by ECMP before sending)                                                                                                                   | 

|**NEW**   |`role`            |`guest` or `associate`. Guest messages get classified + drafted. Associate messages get recorded to conversation state — no classification, no draft.                | 

|**NEW**   |`channel`         |`sms`, `app_chat`, `web_chat`, etc. Per-message because a single TIP.AI session spans channels. TIP.AI uses this to adapt draft length, encoding, and response style.| 

|**NEW**   |`reply_mode`      |`classify_only`, `draft`, or `draft+action`. Controls what TIP.AI returns. See Phasing for when each mode is needed.                                                 | 

|**NEW**   |`phase_mode`      |`shadow`, `preview`, or `live`. Controls visibility of TIP.AI output in the ECMP pipeline. Replaces the existing `shadow_mode` boolean.                              | 

|**EXISTS**|`application_info`|Pass-through: `conversation_id` (ECMP correlation), `message_id` (ECMP archive ID). No change.                                                                       | 

**Guest message example:** 

```json 

{ 

  "prompt": "Do you have EV charging? We're driving down from Orlando", 

  "role": "guest", 

  "channel": "sms", 

  "reply_mode": "draft", 

  "phase_mode": "shadow", 

  "application_info": { 

    "conversation_id": "3b2f9e71-9d9b-47f4-9b2e-3dbd3a7f6a0b", 

    "message_id": "arch_01JKQN4R8T..." 

  } 

} 

``` 

**Associate message example:** 

```json 

{ 

  "prompt": "Hi Sarah! Yes, we have 4 Tesla Superchargers and Level 2 chargers in the garage. I'll make sure your parking spot is near the chargers.", 

  "role": "associate", 

  "channel": "sms", 

  "phase_mode": "shadow", 

  "application_info": { 

    "conversation_id": "3b2f9e71-9d9b-47f4-9b2e-3dbd3a7f6a0b", 

    "message_id": "arch_01JKQP2M9V..." 

  } 

} 

``` 

Note: associate messages do not include `reply_mode` — there is no classification or draft to control. 

### Session Patch — `PATCH /v1/sessions/{id}` 

New endpoint. Called when stay context changes mid-stay: room upgrades, late checkout approvals, service recovery events, Bonvoy tier changes, language preference updates, new stay events. 

**Requirements:** 

- Must not lose conversation history or prior classification state 

- Must support partial updates (only fields being changed) 

- Must support appending to `stay_events` without replacing the array 

**Example — room upgrade + service recovery note:** 

```json 

{ 

  "context": { 

    "reservation": { 

      "roomType": "Presidential Suite" 

    }, 

    "stay_events": [ 

      { 

        "type": "upgrade", 

        "description": "Upgraded to Presidential Suite", 

        "timestamp": "2026-02-16T10:30:00Z", 

        "source": "pms" 

      }, 

      { 

        "type": "service_recovery", 

        "description": "Guest reported AC issue, resolved same day. Engineering confirmed fix.", 

        "timestamp": "2026-02-16T14:00:00Z", 

        "source": "gxp" 

      }, 

      { 

        "type": "late_checkout", 

        "description": "Approved, 2:00 PM", 

        "timestamp": "2026-02-17T08:00:00Z", 

        "source": "associate" 

      } 

    ] 

  } 

} 

``` 

**Proposed response:** 

```json 

{ 

  "session_id": "sess_01JKQM8X7N...", 

  "status": "active", 

  "updated_fields": ["context.reservation.roomType", "context.stay_events"], 

  "conversation_history_preserved": true 

} 

``` 

> TIP.AI may propose an alternative response shape that meets these requirements: confirm what was updated, confirm history was preserved. 

----- 

## Response Contract 

Returned synchronously on every `POST /v1/sessions/{id}/messages`. 

### Guest Message Response 

|Status    |Field                            |Description                                                                                                                                                                                                                               | 

|----------|---------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------| 

|**EXISTS**|`accepted`                       |No change                                                                                                                                                                                                                                 | 

|**EXISTS**|`message_id`                     |TIP.AI message ID — no change                                                                                                                                                                                                             | 

|**EXISTS**|`model_version`                  |No change                                                                                                                                                                                                                                 | 

|**NEW**   |`taxonomy_version`               |Echo of request value. Pins response to taxonomy release.                                                                                                                                                                                 | 

|**NEW**   |`phase_mode`                     |Echo of request value.                                                                                                                                                                                                                    | 

|**EXISTS**|`response`                       |Draft text — must be personalized (guest name, Bonvoy tier, property-specific) and channel-aware (SMS length limits differ from app chat). Used as draft suggestion in associate preview; used as auto-send candidate in deflection phase.| 

|**EXTEND**|`intent_mapping.intent_details[]`|Array of classified intents. Extended from current coarse labels to fine-grained taxonomy.                                                                                                                                                | 

|**EXTEND**|`.bucket_key`                    |Fine-grained taxonomy key (e.g., `HK_REQ_SUPPLIES`, `PROP_EV_CHARGING`). Replaces current coarse label.                                                                                                                                   | 

|**NEW**   |`.category`                      |Top-level group (e.g., `HOUSEKEEPING`, `PROPERTY_INFO`)                                                                                                                                                                                   | 

|**NEW**   |`.confidence`                    |0.0–1.0 float per intent                                                                                                                                                                                                                  | 

|**NEW**   |`.provenance`                    |How TIP.AI classified this intent (e.g., `DETERMINISTIC`, `LLM`, `EMBEDDING`). TIP.AI’s internal implementation detail — ECMP uses for cost efficiency assessment and analytics, not routing.                                             | 

|**NEW**   |`.reason_code`                   |Human-readable classification reason. Optional — TIP.AI may return null. Used for shadow mode evaluation and debugging.                                                                                                                   | 

|**EXISTS**|`.sub_query`                     |Decomposed query text — no change                                                                                                                                                                                                         | 

|**NEW**   |`sentiment`                      |`POSITIVE`, `NEUTRAL`, `NEGATIVE`, or `URGENT`                                                                                                                                                                                            | 

|**NEW**   |`rag.answerability`              |`FULL`, `PARTIAL`, or `NONE`. ECMP routes on this: FULL = deflection candidate, PARTIAL = draft with caveats, NONE = route to human.                                                                                                      | 

|**NEW**   |`rag.sources[]`                  |Source attribution sufficient for ECMP to evaluate grounding quality during shadow mode. TIP.AI proposes the structure.                                                                                                                   | 

|**NEW**   |`telemetry.tokens_used`          |Token count for cost tracking. Required.                                                                                                                                                                                                  | 

|**NEW**   |`telemetry.latency_ms`           |TIP.AI internal processing time. Recommended — helps ECMP distinguish TIP.AI latency from network latency.                                                                                                                                | 

|**EXISTS**|`node_results`                   |Full tool execution trace — no change                                                                                                                                                                                                     | 

|**EXISTS**|`incomplete_nodes`               |Slot filling state — no change                                                                                                                                                                                                            | 

|**EXISTS**|`application_info`               |Pass-through from request — no change                                                                                                                                                                                                     | 

**Note on confidence bands:** ECMP computes confidence bands (HIGH/MED/LOW) internally from the raw float. Thresholds are ECMP business rules (e.g., HIGH ≥ 0.85, MED ≥ 0.60, LOW < 0.60) and may change without TIP.AI involvement. TIP.AI returns the float only. 

**Single intent example:** 

```json 

{ 

  "accepted": true, 

  "message_id": "msg_01JKQN5T2P...", 

  "model_version": "3.4.2", 

  "taxonomy_version": "2026-02-01", 

  "phase_mode": "shadow", 

  "response": "Hi Sarah! Great news — we have 4 Tesla Superchargers and Level 2 chargers right in the parking garage. Since you're driving from Orlando, I can reserve a spot near the chargers for your arrival on the 15th. Safe travels!", 

  "intent_mapping": { 

    "intent_details": [ 

      { 

        "bucket_key": "PROP_EV_CHARGING", 

        "category": "PROPERTY_INFO", 

        "confidence": 0.94, 

        "provenance": "LLM", 

        "reason_code": "Semantic match: EV/charging with property context", 

        "sub_query": "Do you have EV charging?" 

      } 

    ] 

  }, 

  "sentiment": "NEUTRAL", 

  "rag": { 

    "answerability": "FULL", 

    "sources": [] 

  }, 

  "telemetry": { 

    "tokens_used": 342, 

    "latency_ms": 387 

  }, 

  "node_results": [], 

  "incomplete_nodes": [], 

  "application_info": { 

    "conversation_id": "3b2f9e71-9d9b-47f4-9b2e-3dbd3a7f6a0b", 

    "message_id": "arch_01JKQN4R8T..." 

  } 

} 

``` 

> **Note on `rag.sources`:** The example above shows an empty array. TIP.AI to propose source attribution structure during implementation. ECMP needs sufficient detail to evaluate whether responses are grounded in real property data during shadow mode. 

**Multi-intent example:** 

Guest sends: “Is parking free? Also can I get late checkout on the 18th” 

```json 

{ 

  "accepted": true, 

  "message_id": "msg_01JKQN9K5R...", 

  "model_version": "3.4.2", 

  "taxonomy_version": "2026-02-01", 

  "phase_mode": "shadow", 

  "response": "Hi Sarah! I can help with both. We have complimentary valet for Titanium Elite members — just pull up to the main entrance on arrival. For late checkout, I've noted your request and we'll confirm availability the morning of the 18th. As a Titanium Elite member, we can usually accommodate up to 4 PM.", 

  "intent_mapping": { 

    "intent_details": [ 

      { 

        "bucket_key": "TRANS_PARKING_INFO", 

        "category": "TRANSPORTATION", 

        "confidence": 0.91, 

        "provenance": "LLM", 

        "reason_code": "Parking question with tier-based pricing context", 

        "sub_query": "Is parking free?" 

      }, 

      { 

        "bucket_key": "ARR_LATE_CHECKOUT", 

        "category": "ARRIVAL_DEPARTURE", 

        "confidence": 0.88, 

        "provenance": "LLM", 

        "reason_code": "Late checkout request with specific date", 

        "sub_query": "Can I get late checkout on the 18th" 

      } 

    ] 

  }, 

  "sentiment": "NEUTRAL", 

  "rag": { 

    "answerability": "PARTIAL", 

    "sources": [] 

  }, 

  "telemetry": { "tokens_used": 518, "latency_ms": 623 }, 

  "application_info": { 

    "conversation_id": "3b2f9e71-9d9b-47f4-9b2e-3dbd3a7f6a0b", 

    "message_id": "arch_01JKQN8H3Q..." 

  } 

} 

``` 

PARTIAL answerability because parking info is answerable from property catalog but late checkout requires a PMS availability check. 

### Associate Message Response 

When `role: associate` is sent, TIP.AI records the message to conversation history, tracks intent resolution, and extracts stay events. No classification, no draft. 

```json 

{ 

  "accepted": true, 

  "message_id": "msg_01JKQP3N4W...", 

  "model_version": "3.4.2", 

  "taxonomy_version": "2026-02-01", 

  "phase_mode": "shadow", 

  "response": null, 

  "intent_mapping": { "intent_details": [] }, 

  "sentiment": null, 

  "rag": null, 

  "extracted_events": [ 

    { 

      "type": "commitment", 

      "description": "Parking spot reserved near EV chargers", 

      "source": "associate_message" 

    } 

  ], 

  "telemetry": { "tokens_used": 0, "latency_ms": 12 }, 

  "application_info": { 

    "conversation_id": "3b2f9e71-9d9b-47f4-9b2e-3dbd3a7f6a0b", 

    "message_id": "arch_01JKQP2M9V..." 

  } 

} 

``` 

> **Note:** `extracted_events` is a new capability. TIP.AI may return an empty array initially and add extraction logic over time. ECMP persists any returned events and may PATCH them back to the session as `stay_events`. See Phasing for rollout expectations. 

### Error Response 

Standard error envelope across all endpoints. ECMP uses error codes for circuit breaker logic and retry decisions. 

```json 

{ 

  "error": { 

    "code": "CLASSIFICATION_TIMEOUT", 

    "message": "Classification exceeded P99 threshold (2000ms)", 

    "request_id": "req_01JKQN4R8T...", 

    "timestamp": "2026-02-15T14:30:22.456Z" 

  } 

} 

``` 

**ECMP requires the ability to distinguish these failure modes:** 

|Error Category          |ECMP Action                             | 

|------------------------|----------------------------------------| 

|Classification timeout  |Route to human unclassified             | 

|Taxonomy version unknown|Fall back to latest known version       | 

|Session not found       |Create new session, retry message       | 

|Rate limited            |Backoff + queue                         | 

|Internal error          |Circuit breaker after sustained failures| 

How TIP.AI maps internal errors to these categories is an engineering decision. ECMP needs to distinguish these modes; the exact string codes are negotiable. 

----- 

## What ECMP Delivers to TIP.AI 

|Artifact                                  |Description                                                                                                                                                                                                                                               | 

|------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------| 

|**Taxonomy CSV (versioned)**              |Full set of `bucket_key` values across categories. Per key: category, description, actionability tier (1–5), route type. Built from discovery work on 530K+ real guest messages. Will evolve — `taxonomy_version` pins each message to a specific release.| 

|**Classification logic profiles**         |Per-intent: keyword hints, regex patterns, followup mode, priority. TIP.AI can use these however makes sense for their implementation — these are patterns ECMP already knows work.                                                                       | 

|**Adversarial test suite**                |Validated against real guest messages. Expected `bucket_key` per test case. TIP.AI validates classification accuracy against this before any phase gate.                                                                                                  | 

|**Brand voice configurations (versioned)**|Per-brand: tone guidelines, channel behavior rules (e.g., SMS length constraints), response style directives. ECMP maintains, `brand_voice_version` pins each session. Delivery mechanism (registry, API, config sync) to be agreed with TIP.AI.          | 

----- 

## Integration Requirements Summary 

These are the contract requirements ECMP needs met. How TIP.AI implements them is an engineering decision for Paul’s team. 

|# |Requirement                         |Detail                                                                                                                                                                                                                                 | 

|--|------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------| 

|1 |**Fine-grained classification**     |TIP.AI loads ECMP’s hospitality taxonomy and returns `bucket_key` in `intent_details[]`. The current coarse labels do not cover what ECMP needs. ECMP provides taxonomy CSV, classification logic profiles, and adversarial test suite.| 

|2 |**Per-intent confidence scoring**   |`confidence` (0.0–1.0 float) per intent in `intent_details[]`. Not at the response level — per intent. ECMP computes bands internally from the float.                                                                                  | 

|3 |**Structured context consumption**  |ECMP sends a structured `context` object (guest, reservation, stay_events) at session creation and per-PATCH. TIP.AI must consume this for personalization, RAG grounding, and classification context.                                 | 

|4 |**Role-aware message handling**     |ECMP sends `role` (`guest` or `associate`) on every message. Guest messages get classified and drafted. Associate messages get recorded to conversation state — no classification, no draft.                                           | 

|5 |**Phase mode enum**                 |`shadow_mode` boolean replaced with `phase_mode`: `shadow`, `preview`, or `live`. Controls visibility of TIP.AI output in the ECMP pipeline.                                                                                           | 

|6 |**Session PATCH endpoint**          |`PATCH /v1/sessions/{id}` to update context on a live session. Must support partial updates and `stay_events` append. Must not lose conversation history or prior classification state.                                                | 

|7 |**Channel-aware drafting**          |ECMP sends `channel` per-message. TIP.AI adapts draft length, encoding, and response style per channel.                                                                                                                                | 

|8 |**Personalized response generation**|TIP.AI uses session context in every draft — guest name, Bonvoy tier, property-specific amenities, actual reservation details, guest’s preferred language.                                                                             | 

|9 |**Brand voice consumption**         |TIP.AI resolves brand voice from versioned configurations provided by ECMP. `brand_code` + `brand_voice_version` on session creation.                                                                                                  | 

|10|**Stay event extraction**           |TIP.AI extracts stay-relevant events (commitments, service actions) from associate messages and returns them in `extracted_events[]`. ECMP persists and may PATCH back to session.                                                     | 

|11|**Provenance tracking**             |`provenance` field per intent indicating how classification was made. ECMP uses for cost efficiency assessment, not routing.                                                                                                           | 

----- 

## Phasing 

Aligned to the Enterprise Chat Guest Messaging product roadmap. Phase gates are defined in the product roadmap and based on shadow mode evaluation metrics. 

|Phase                      |Target    |TIP.AI Delivers                                                                                                                                                                                             |ECMP Delivers                                                                                                                        |`reply_mode`            | 

|---------------------------|----------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------|------------------------| 

|**1 — Shadow**             |Q1–Q2 2026|`bucket_key` + `confidence` + `sentiment` in response. Taxonomy loaded. Structured context consumed. `response` text = personalized draft (logged only, evaluated for accuracy and personalization quality).|PII/CC redaction in pipeline. Context packaging. Brand voice configs delivered. Taxonomy CSV + test suites delivered. Shadow logging.|`classify_only`, `draft`| 

|**2 — Associate Preview**  |Q2–Q3 2026|RAG answerability gating (`FULL`/`PARTIAL`/`NONE`). `response` text surfaced as draft suggestion to associates. Stay event extraction from associate messages.                                              |Draft surfaced in GxP. Approve/edit/discard workflow. Curated quick-reply templates alongside AI suggestions.                        |`draft`                 | 

|**3 — Deflection Eligible**|Q3+ 2026  |Action suggestions. Expanded RAG coverage across more intent categories.                                                                                                                                    |Auto-send for pure-info intents (ECMP-computed confidence band = HIGH, RAG = FULL). Rate limits and circuit breakers.                |`draft+action`          | 

----- 

## Degradation Handling 

If TIP.AI is unavailable or exceeds the timeout threshold, ECMP routes the message to the associate unclassified. The message still gets archived, evidence-chained, and delivered to GxP — the associate simply does not receive a classification or draft suggestion. There is no guest impact. 

ECMP tracks TIP.AI availability and will circuit-break after sustained failures to avoid queuing latency. 

----- 

## Non-Functional Requirements 

|Requirement         |Target                             |Notes                                                                                                                                                                       | 

|--------------------|-----------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------| 

|**Response latency**|P95 < 2000ms                       |Synchronous response including classification + draft. ECMP will timeout and route to human unclassified beyond this threshold. To be confirmed with TIP.AI for feasibility.| 

|**Availability**    |Aligned to OSD platform standards  |TIP.AI degradation does not impact guest message delivery — only classification and draft quality.                                                                          | 

|**Idempotency**     |TIP.AI deduplicates on `message_id`|ECMP may retry on timeout. Duplicate processing must not corrupt session state.                                                                                             | 

----- 

## Scope Boundary 

**ECMP owns:** Consent enforcement (TCPA compliance, fail-closed), template registry, Syniverse delivery, DLR handling, right-to-be-forgotten, evidence chains, PII/CC redaction, send/no-send decision, confidence band computation, MDP evaluation pipeline, kill switch / feature flags. 

**TIP.AI owns:** Classification, confidence scoring, sentiment analysis, RAG (data sourcing + answerability assessment), draft response generation, prompt assembly, guardrail enforcement, conversation history management, stay event extraction, brand voice application, taxonomy hosting. 

**Joint — delivery mechanism TBD:** Brand voice configuration sync, taxonomy delivery, adversarial test suite delivery, RAG source attribution structure, PATCH response shape. 

----- 

## MDP Integration 

All TIP.AI responses are persisted by ECMP and shared with MDP for evaluation. This is how ECMP validates classification quality at scale during shadow mode and tracks model performance over time. No additional TIP.AI work is needed — ECMP handles the MDP pipeline. 

----- 

## Next Steps 

Once Paul’s team confirms feasibility and timeline against these requirements, this document evolves into the formal integration specification. 

Open items for the first working session: 

1. Confirm single-session-per-stay model works with TIP.AI’s session architecture (OQ-1) 

2. Agree on brand voice and taxonomy delivery mechanism 

3. TIP.AI proposes RAG source attribution structure 

4. Confirm P95 < 2000ms latency target feasibility 

5. Align on PATCH semantics (partial update, stay_events append) 

----- 

	*ECMP × TIP.AI Integration Requirements | ECMP-TIPAI-INT-002 v3.0 | February 2026 | Rami (ECMP Architecture