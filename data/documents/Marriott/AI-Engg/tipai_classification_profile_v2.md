# Intent Classification & RAG Assessment Profile
## For TIP.AI Integration

---

## 1. System Overview

**Purpose:** Classify guest messages → route to correct bucket → assess if RAG can auto-respond

**Core Principle:** Deterministic rules WIN when matched. LLM is fallback only.

---

## 2. Classification Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                    MESSAGE INPUT                            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  PRE-SCAN (flags only, doesn't route)                       │
│  • is_safety_urgent (911, fire, assault, weapon)            │
│  • is_complaint_signal (disappointed, unacceptable)         │
│  • is_pure_ack (thanks, ok, 好的, gracias)                   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  GUARDS (blocking)                                          │
│  • Payment PII → redact, route to human                     │
│  • Non-Latin >20% → route to human (except CJK acks)        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  DETERMINISTIC ROUTING (if match → LOCKED, skip LLM)        │
│  Priority order:                                            │
│    1. Safety keywords (if flagged)                          │
│    2. App button exact matches (multilingual)               │
│    3. Typed request exact matches                           │
│    4. Regex patterns (upgrade, parking, shuttle, etc.)      │
│    5. Pure ack → GENERAL_ACK                                │
│    6. Followup mode (qty/time from prev turn)               │
└─────────────────────────────────────────────────────────────┘
                            │
                     No match?
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  LLM CLASSIFICATION (fallback)                              │
│  • Case-level batch (all messages in conversation)          │
│  • Context: prev_bucket_key, prev_category, weak hints      │
│  • Output: bucket_key, confidence, extracted_item           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  POST-GUARDS (sanity checks)                                │
│  • FNB reservation needs dining keywords                    │
│  • SAFETY needs pre-scan flag                               │
│  • LOCAL needs recommendation signals                       │
│  → Downgrade to GENERAL_UNCLEAR if guard fails              │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  RAG ASSESSMENT (if bucket is RAG-eligible)                 │
│  • Load property data for bucket                            │
│  • Assess: FULL / PARTIAL / NONE                            │
│  • Generate draft_response if answerable                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Key Nuance Handling

### 3.1 Embedded Acknowledgments

**Rule:** Request signals DISQUALIFY pure ack classification.

```
REQUEST_SIGNALS = {can, could, please, need, want, ?, what, where, when, how}

"Thanks!"                    → GENERAL_ACK (no request signal)
"Thanks! Can I get towels?"  → HK_REQ_SUPPLIES (request wins)
"Perfect, breakfast hours?"  → FNB_INFO_BREAKFAST (? = request)
```

### 3.2 Fragment / Followup Handling

**Rule:** Numeric-only messages inherit meaning from previous turn's followup_mode.

```
CONFIG per bucket:
  HK_REQ_SUPPLIES     → followup_mode: QTY
  DEP_REQ_LATE_CHECKOUT → followup_mode: TIME

CONVERSATION:
  Turn 1: "Can I get towels?"     → HK_REQ_SUPPLIES
  Turn 2: "3"                     → HK_REQ_SUPPLIES (Qty: 3)

  Turn 1: "Late checkout?"        → DEP_REQ_LATE_CHECKOUT  
  Turn 2: "11"                    → DEP_REQ_LATE_CHECKOUT (Time: 11:00)
```

**"Same" / "Ditto" Pattern:**
```
Turn 1: "Towels for room 101"     → HK_REQ_SUPPLIES, room=101
Turn 2: "Same for 102"            → HK_REQ_SUPPLIES, room=102
```

### 3.3 Checkout Disambiguation

| Message                  | Classification          | Why                           |
| ------------------------ | ----------------------- | ----------------------------- |
| "Checking out tomorrow"  | DEP_REQ_CHECKOUT_NOTIFY | Statement (notification)      |
| "Late checkout please"   | DEP_REQ_LATE_CHECKOUT   | Request with "please"         |
| "Checkout at 1pm"        | DEP_REQ_LATE_CHECKOUT   | Time specified = late request |
| "What time is checkout?" | ARR_INFO_TIMES          | Question about policy         |

### 3.4 Safety Precision

| Message                  | Classification        | Why                         |
| ------------------------ | --------------------- | --------------------------- |
| "Smoke in my room!"      | SAFETY_EMERG_FIRE     | Explicit fire indicator     |
| "Room smells like smoke" | MAINT_PROB_SMELL      | Odor complaint, not fire    |
| "Call 911"               | SAFETY_EMERG_SECURITY | Explicit emergency phrase   |
| "This is an emergency"   | (needs more context)  | Vague - check for specifics |

---

## 4. RAG Answerability Assessment

### 4.1 Purpose

**The bucket is already assigned.** RAG assessment asks: *Does the property data mapped to this bucket have enough information to answer this specific guest question?*

```
Classification: TRANS_INFO_PARKING
                      ↓
Bucket maps to MARSHA fields: [parking_fee, valet_fee, parking_hours, ev_charging]
                      ↓
Property BOSCO data: { parking_fee: "$45/day", valet_fee: null, parking_hours: "24hr", ev_charging: null }
                      ↓
Guest asks: "How much is valet?"
                      ↓
Assessment: NONE (data_missing) — valet_fee is null for this property
```

### 4.2 Bucket → MARSHA Field Mapping

Each bucket has a predefined set of MARSHA fields it needs:

| Bucket               | Required MARSHA Fields                                               |
| -------------------- | -------------------------------------------------------------------- |
| `ARR_INFO_TIMES`     | check_in_time, check_out_time, early_checkin_policy                  |
| `TRANS_INFO_PARKING` | parking_fee, valet_fee, parking_hours, ev_charging                   |
| `FNB_INFO_BREAKFAST` | breakfast_hours, breakfast_included, breakfast_cost, restaurant_name |
| `AMEN_INFO_POOL`     | pool_hours, pool_indoor, pool_heated, pool_location                  |

### 4.3 Assessment Levels

| Level | Meaning | Action |
|-------|---------|--------|
| **FULL** | Property has all mapped fields needed for this question | Auto-respond |
| **PARTIAL** | Property has some data, but not everything asked | Auto-respond what we have + flag gap |
| **NONE** | Property data doesn't cover what guest asked | Route to human |

### 4.4 NONE Reasons

| Reason | Meaning | Root Cause |
|--------|---------|------------|
| `data_missing` | Right bucket, but property lacks this field | **Catalog gap** - enrich MARSHA data |
| `topic_mismatch` | Question doesn't match bucket's domain | **Misclassification** - wrong bucket |
| `not_a_question` | Pure ack/statement, nothing to answer | **No action needed** |
| `unclear` | Can't determine what specific data is needed | **Ambiguous** - ask clarifying question |

### 4.5 Ambiguity Detection

Messages flagged as ambiguous get **conversation context injected**:

**Ambiguous Indicators:**
- Pronouns: "Is **it** available?", "How much is **that**?"
- Continuations: "And breakfast?", "Same for tomorrow?"
- Short fragments: "yes", "3", "11am"
- References: "I was told...", "As mentioned..."

**Context Injection:**
```
PRIOR MESSAGES:
[MSG 1]: What time does the pool open?
[MSG 2]: Thanks!

CURRENT MESSAGE: "And the gym?"

→ Interpreted: Guest asking about gym hours
```

### 4.6 Output Schema

```json
{
  "answerability": "FULL",
  "confidence": "HIGH",
  "draft_response": "The pool is open 6 AM to 10 PM daily.",
  "missing_data": null,
  "detected_intents": ["pool hours"],
  "is_multi_intent": false,
  "bucket_seems_correct": true
}
```

---

## 5. Conversation State Tracking

### Required State (per conversation)

```
prev_bucket_key: str      # Last non-ACK bucket
prev_category: str        # For context hints  
prev_item: str            # Extracted item (room, qty, etc.)
turn_count: int           # Message index
```

### State Flow Example

```
MSG 1: "Pool hours?"
  → bucket: AMEN_INFO_POOL
  → state: prev_bucket_key=AMEN_INFO_POOL

MSG 2: "Thanks"  
  → bucket: GENERAL_ACK
  → state: prev_bucket_key=AMEN_INFO_POOL (unchanged - acks don't update)

MSG 3: "And breakfast?"
  → context hint: prev was AMEN_INFO_POOL
  → bucket: FNB_INFO_BREAKFAST
  → state: prev_bucket_key=FNB_INFO_BREAKFAST
```

---

## 6. Deterministic Pattern Reference

### App Button Exact Matches (sample)

```
English:          Chinese:          Japanese:
"Room Service"    "客房服务"         "ルームサービス"
"Housekeeping"    "客房清洁"         "ハウスキーピング"
"Checkout"        "退房"            "チェックアウト"
```

### Regex Patterns (key ones)

| Pattern | Bucket |
|---------|--------|
| `upgrade.*(room\|suite)` | RES_REQ_UPGRADE |
| `(bell\|bellman\|luggage\|bags?)` | HK_REQ_BELLBOY |
| `(cancel\|modify).*(reservation\|booking)` | RES_REQ_CANCEL_MODIFY |
| `(shuttle\|airport).*(time\|schedule)` | TRANS_INFO_SHUTTLE |
| `(pool\|gym).*(hour\|open\|close)` | AMEN_INFO_* (domain-specific) |

---

## 7. Diagrams

<!-- INSERT DIAGRAMS HERE -->
<!-- See separate diagrams file for eraser.io specs -->

---

## 8. TIP.AI Integration Checklist

### Must Implement

- [ ] Pre-scan flags (safety, complaint, ack) before routing. -- Functions to handle this scenarios
- [ ] Deterministic routing with priority (exact match > regex > LLM). - App buttons, keyword exact match, orchestration 
- [ ] Request signal detection (disqualifies pure ack) -- Informational request, request have action taken - such as RAG vs non RAG prompt
- [ ] Followup mode per bucket (QTY vs TIME). --  Quantity - house keeping items, Time - parking, checkout and other timings restaurants -- Context retrieval 
- [ ] Conversation state tracking (prev_bucket_key) - Context retrieval 
- [ ] Ambiguity detection for RAG context injection 
	- [ ] No duplicate answers 
- [ ] Post-classification sanity guards - 


Rules Engine - Certain action against the criteria for the intents and guidelines  ( TIP AI System - intent DB)

### Configuration Needed

| Setting | Value |
|---------|-------|
| QTY range | 1-20 |
| TIME range | 0-23 (hours) |
| Short message | ≤2 words or <15 chars |
| Non-Latin threshold | ≥20% of characters |
| Context window for LLM | Last 5 messages |

### Test Cases (Critical)

```
# Embedded acks
"Thanks! Need towels"           → HK_REQ_SUPPLIES
"Perfect, also breakfast?"      → FNB_INFO_BREAKFAST

# Fragments (after context)
"3" (after supplies request)    → HK_REQ_SUPPLIES (Qty: 3)
"11am" (after checkout ask)     → DEP_REQ_LATE_CHECKOUT (Time: 11:00)

# Safety precision  
"smoke in my room"              → SAFETY_EMERG_FIRE
"room smells like smoke"        → MAINT_PROB_SMELL

# Checkout variants
"checking out"                  → DEP_REQ_CHECKOUT_NOTIFY
"late checkout please"          → DEP_REQ_LATE_CHECKOUT
"checkout time?"                → ARR_INFO_TIMES
```

---

## 9. Output Fields Reference

| Field | Description |
|-------|-------------|
| `bucket_key` | Classification result (e.g., HK_REQ_SUPPLIES) |
| `method` | How classified (DETERMINISTIC, LLM, PURE_ACK, etc.) |
| `confidence` | HIGH / MEDIUM / LOW |
| `extracted_item` | Parsed value (room number, quantity, time) |
| `answerability` | FULL / PARTIAL / NONE (RAG assessment) |
| `draft_response` | Auto-generated response (if FULL/PARTIAL) |
| `none_reason` | Why NONE (topic_mismatch, data_missing, etc.) |
| `is_multi_intent` | True if multiple topics detected |
