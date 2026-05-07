# Progress Log

## Session: 2026-03-24 (LLM Proxy — Route All LLM Calls Through Backend)

### New `routers/llm_proxy.py` — 5 endpoints under `/api/llm`
- `GET /api/llm/config` — read current LLM config (endpoints, masked key)
- `PUT /api/llm/config` — update LLM config (stored in `settings` table as `llm_config` key)
- `GET /api/llm/models?backend=` — list models via backend proxy
- `POST /api/llm/chat` — streaming chat completion proxy (SSE for LiteLLM, NDJSON for Ollama)
- `POST /api/llm/chat/sync` — non-streaming chat completion proxy

### Config priority: DB settings → env vars → defaults
- LLM endpoints and API key are stored in the `settings` table (key: `llm_config`)
- Falls back to `OLLAMA_ENDPOINT`, `LITELLM_API_BASE`, `LITELLM_API_KEY` env vars
- UI modal on workbench page allows editing endpoints and API key

### Frontend: unified proxy functions in `llm.js`
- Removed `LITELLM_ENDPOINT`, `OLLAMA_ENDPOINT`, `_serverApiKey` globals
- Removed `_loadEndpoints()` (no longer fetches secrets from `/api/config/frontend`)
- Added `callLLM(messages, model, targetDiv)` — unified streaming via `/api/llm/chat`
- Added `callLLMSync(backend, model, messages)` — non-streaming via `/api/llm/chat/sync`
- Added `fetchModels(backend)` — model listing via `/api/llm/models`
- Added `streamNDJSON(resp, targetDiv)` — Ollama NDJSON stream parser (extracted from old `callOllama`)
- Kept `streamSSE()`, `buildSystemPrompt()`, all prompt helpers unchanged

### page-workbench.js cleanup
- Deleted duplicate `callLiteLLM()`, `callOllama()`, `streamSSE()` (were shadowing llm.js)
- All 3 streaming call sites → `callLLM()`
- Replaced `fetchOllamaModels()`/`fetchLiteLLMModels()` → `fetchWorkbenchModels()` using `fetchModels()`
- Simplified `connectWorkbench()` to use `fetchModels()`
- Removed `apiKey` from `saveWbSettings()`/`restoreWbSettings()`
- Added LLM config modal (endpoints + API key) with `openLlmConfigModal()`/`saveLlmConfig()`

### page-ragresults.js cleanup
- `rrConnect()` and `rrConnectJudge()` now use `fetchModels()` instead of direct endpoint calls
- Removed all `window._llmApiKey` stashing and IndexedDB API key retrieval
- Both eval call sites → `callLLM()`

### page-readiness.js cleanup
- `irGenConnect()` now uses `fetchModels()` instead of direct endpoint calls
- Deleted `callLLMNonStreaming()` function entirely
- Call site → `callLLMSync()` (from llm.js)
- Removed `apiKey` parameter from generation flow

### Security: `/api/config/frontend` stripped
- No longer returns `litellm_api_key`, `litellm_endpoint`, or `ollama_endpoint`
- Only returns `env` (environment name)
- API key input removed from workbench HTML, replaced with config button
- API key input removed from readiness HTML, replaced with "Server-side" indicator

---

## Session: 2026-03-24 (System Prompt Template Versioning)

### New `prompt_templates` table and DB seed
- Created `prompt_templates` table: `id`, `name`, `description`, `rules_rag`, `rules_handoff`, `json_schema`, `voice_instructions`, `conversational_fallback`, `is_default`
- Migration adds `prompt_template_id` column to `workbench_assessments`
- On init, seeds a "Default" template with hardcoded values from `llm.js` if table is empty

### Template CRUD API (7 endpoints under `/api/workbench/templates`)
- GET list, GET by ID, POST create, PUT update, DELETE (non-default only), POST clone, PUT set-default
- Pydantic models: `PromptTemplateCreate`, `PromptTemplateUpdate`

### Frontend: templatized `buildSystemPrompt()` in `llm.js`
- Extracted hardcoded rules/schema into `DEFAULT_RULES_RAG`, `DEFAULT_RULES_HANDOFF`, `DEFAULT_JSON_SCHEMA` constants
- `buildSystemPrompt()` reads from `window.activePromptTemplate` with fallback to defaults
- `getBrandVoicePrompt()` checks template voice fields as intermediate priority

### Frontend: replaced IndexedDB voice profiles with DB-backed templates
- `page-workbench.js`: `loadPromptTemplates()` fetches from API, `setActiveTemplate()` populates UI
- Migration: on first load, existing `_wbPromptVersions` from IndexedDB are auto-migrated to DB templates
- All CRUD operations (save, update, rename, delete, clone) now hit the API

### UI: expanded Voice Profile modal to Prompt Template modal
- Added collapsible "Rules & Schema" section with RAG rules, handoff rules, JSON schema textareas + reset buttons
- Renamed trigger and modal header from "Voice Profile" to "Prompt Template"
- Template list shows DEFAULT badge, clone button, prevents deleting default

### Assessment tracking
- `_buildAssessment()` now includes `prompt_template_id` alongside `prompt_version`
- CSV export headers include `prompt_template_id`

### Intent readiness: template awareness
- SQL query includes `prompt_template_id` in examples SELECT
- CSV export includes `prompt_template_id` column
- JSON API includes `prompt_template_id` per example

### API client (`apiClient.js`)
- Added 7 methods: `getPromptTemplates`, `getPromptTemplate`, `createPromptTemplate`, `updatePromptTemplate`, `deletePromptTemplate`, `clonePromptTemplate`, `setDefaultTemplate`

---

## Session: 2026-03-24 (Readiness — Enrich CSV Export)

### Expanded `/api/readiness/export` from summary-only to one-row-per-example
- **Before:** CSV had one row per intent with only taxonomy/coverage/eval/status columns — no actual assessment data
- **After:** CSV emits one row per assessment example, including: `guest_message`, `generated_response`, `answerability`, `confidence`, `reasoning`, `model`, `backend`, `brand_voice_tone`, `brand_voice_persona`, `prompt_version`, `batch_name`, `generated_at`, plus taxonomy and readiness columns
- Intents with no examples still get one row (empty assessment columns) so full intent list is always visible
- Dropped `coverage_gaps` and eval score columns from CSV (eval data is better suited for its own export)

### Expanded `/api/readiness/intents` JSON examples with new fields
- Added to SQL SELECT and examples_map: `reasoning`, `brand_voice_tone`, `brand_voice_persona`, `prompt_version`, `backend`, `route`, `notes`, `batch_name`
- JSON API now returns these fields per example — available for future UI use

---

## Session: 2026-03-23 (Readiness — Fix "no classified messages" skip bug)

### Removed `prop_code_map` JOIN from `/api/readiness/samples`
- **Bug:** Readiness generation skipped intents with "no classified messages" even though messages existed in `classification_rows` — the JOIN with `prop_code_map` filtered out cases whose `id_case` wasn't in that table
- **Fix:** Query now selects directly from `classification_rows` by `bucket_key` + `message_role='CUSTOMER'`, with null/empty guards — no property filter needed for readiness
- **Scope:** Only affects readiness; workbench continues using `prop_code_map` for property-specific queries
- **API compat:** `property` param kept in function signature but unused

---

## Session: 2026-03-23 (TIP.AI Integration Guide)

### Replaced `TIPAI_HANDOFF_SPEC.md` with polished `TIPAI-INTEGRATION.md`
- **14 sections** in dashboard doc style (H1 title + blockquote intro + related docs links, Mermaid diagrams, tables)
- **Perspective reframe:** We are Chat/ECMP, they are TIP.AI — doc explains how we integrate, not just what to hand off
- **Mermaid diagrams:** End-to-end architecture flow, 7-phase pipeline flowchart, future single-call flow, multi-turn conversation state, routing decision engine
- **Section 4: Classification Deep Dive** — all 7 phases with patterns, rules, tables, and outputs
- **Section 5: RAG Assessment** — `buildSystemPrompt()` logic, assessment JSON schema, route-specific behavior, NONE reasons
- **Section 8: Dashboard Data Contract** — Rosetta Stone mapping table (TIP.AI response fields → dashboard columns), import endpoints, full `workbench_assessments` schema (~50 cols)
- **Section 11: Edge Cases** — 40+ test cases: embedded acks, followup inference, checkout disambiguation, safety precision, sanity guards, language guards
- **Section 13: Phasing** — 3-phase rollout (Shadow → Associate Preview → Deflection) with component matrix and latency budget
- **Section 14: Checklist** — what TIP.AI must implement vs what dashboard must build/change
- **app.py:** Updated `_DOCS_INDEX` entry from `TIPAI_HANDOFF_SPEC` to `TIPAI-INTEGRATION` with new title/desc
- **Cleanup:** Removed `v2/docs/TIPAI_HANDOFF_SPEC.md`

---

## Session: 2026-03-23 (Readiness — Real Messages + Assessment Pipeline)

### Readiness generation rewrite: real messages + workbench assessment flow
- **New endpoint:** `GET /api/readiness/samples` — queries `classification_rows` joined with `prop_code_map` to fetch real guest messages for a given property+intent, returns random sample
- **New endpoint:** `DELETE /api/readiness/examples` — bulk deletes all `workbench_assessments` for a property+intent
- **apiClient:** Added `getReadinessSamples(prop, intent, count)` and `deleteIntentExamples(prop, intent)`
- **processJob rewrite:** Two-step pipeline — (1) fetch real message from classification data, fall back to LLM if none exist; (2) assess using `buildSystemPrompt()` from `llm.js` (full property data, taxonomy, brand voice, capabilities) instead of trivial prompt; saves with real answerability (FULL/PARTIAL/NONE), confidence, reasoning
- **pageInit:** Pre-loads `taxonomyLookup` and `marshaMapping` via `dataStore.getCached()` so `buildSystemPrompt` works on the readiness page
- **openGenModal:** Pre-fills backend from `window.workbenchBackend`, API key from `_serverApiKey`, auto-triggers `irGenConnect()` to load model list on open
- **Delete UI:** Per-example trash icon on each card, "Clear All" button per intent in examples header; both update local data and re-render
- **Answerability badges:** Updated colors to match FULL (green) / PARTIAL (yellow) / NONE (red) instead of old ANSWERABLE/NOT_ANSWERABLE
- **Docs:** Updated WORKBENCH-GUIDE.md section 12 with new endpoints, generation pipeline, and delete features; updated PROGRESS-LOG.md

---

## Session: 2026-03-23 (Intent Readiness Page)

### New page: Intent Readiness (`/readiness`)
- **Database:** Added `intent_readiness` table to Group D with composite PK `(property, intent)`, supports upsert via `ON CONFLICT`
- **Model:** Added `IntentReadinessUpsert` Pydantic model
- **Router:** Created `v2/routers/intent_readiness.py` with 4 endpoints — GET readiness rows, PUT upsert, GET aggregated intents (3-query batch: taxonomy+MARSHA+readiness, examples, eval scores), GET CSV export
- **App:** Registered in `PAGE_META` (after "Eval & Feedback", before "Help & Docs"), imported and included router
- **apiClient:** Added `getReadiness`, `getReadinessIntents`, `setReadiness` methods
- **Template:** Created `v2/templates/pages/readiness.html` — summary bar (5 metric cards), filter row (property, route, RAG mode, status, search), accordion container
- **Frontend JS:** Created `v2/static/js/page-readiness.js` — property dropdown from `/api/prop-catalog/unique-codes`, client-side filtering, category-grouped accordion with route-order sorting, Ready/Not Ready toggles with instant API persist, LLM-powered example generation via `callLiteLLM()`, CSV export via direct download link
- **Docs:** Updated WORKBENCH-GUIDE.md with section 12 (Intent Readiness Page), updated PROGRESS-LOG.md

---

## Session: 2026-03-23 (Demo Mode — Auto-Pilot Videos)

### Demo mode system
- Created `demo-mode.js` — autopilot engine that drives the real dashboard for screen recordings
- Created `demo-mode.css` — overlay styles for narration bar, spotlight mask, progress bar, controls, launcher modal
- Three audience scripts (~60s each): **Executives** (ROI/automation), **Product Managers** (capabilities/eval quality), **Engineers** (architecture/trace/eval)
- State persists across page navigations via `sessionStorage`; resumes after page loader animation
- Spotlight SVG mask highlights target elements with teal glow pulse
- Narration bar at bottom with audience-colored badge
- Control strip: Play/Pause, Skip, Stop + elapsed timer
- Keyboard shortcuts: Space (pause), Escape (stop), ArrowRight (skip)
- Launcher modal triggered by "Demo" button in topbar — 3 audience cards
- Workbench steps: auto-fills property code, types message char-by-char, waits for LLM response, opens trace tab

### Optimize: Taxonomy message feedback — moved filtering to server
- **Before:** Frontend loaded entire `classificationData` array (tens of thousands of rows) into memory via IndexedDB, then filtered in JS with `.toLowerCase()` per row per search.
- **After:** `applyMsgFeedbackFilter()` now calls `GET /api/classification/search` with query params — filtering, text search (ILIKE), taxonomy JOINs, and pagination all happen in PostgreSQL.
- **Backend `search` endpoint enhanced:** Added `method` filter param, `offset` param for pagination, `confidence` column in SELECT, and returns `{rows, total}` for server-side pagination.
- **`apiClient.searchClassification`:** Added `method` and `offset` params.
- **Server-side pagination:** `goMsgPage()` fetches a fresh page from the server instead of re-slicing a giant local array. Only 50 rows transferred per page.
- **Stale request abort:** New `AbortController` cancels in-flight requests when user changes filters before previous search completes.
- **Cached bucket options HTML:** `_getBucketOptionsHtml()` builds dropdown `<option>` HTML once and reuses across all rows. Sets `selected` via DOM after render.

### Bug fix: Eval runs — Details button + feedback not saving
- **Details button:** Changed `evalRuns.indexOf(run)` to pass `run.runId` directly, avoiding stale index after array re-assignment. `showEvalResultDetail` now finds run by ID instead of numeric index.
- **Server `add_result`:** Changed from `INSERT ... execute()` to `INSERT ... RETURNING id` via `fetchrow()`, so the new result's DB id is returned to the client.
- **Client `addEvalResult`:** After saving each result, captures `saved.id` and assigns it to `lastResult.dbId` so feedback persistence works immediately.
- **Lazy-load with `dbId` gap:** If a completed run's results lack `dbId` (e.g., results from a live run where the server failed to return ids), `showEvalRun()` now forces a re-fetch from the server to get proper `dbId` values.
- **Null guard:** Added `(run.config_snapshot || {}).thresholds` guard in `renderEvalRunResults()` to prevent crash when `config_snapshot` is null.

---

## Session: 2026-03-22 (Eval Result Detail Modal Overhaul)

### Eval result detail modal — 5-section layout
- Restructured the eval result detail modal into 5 clearly separated sections:
  1. **Test Case Input** — original message, intent, property, expected values
  2. **Generation Output** — draft response, answerability, confidence, reasoning
  3. **Judge Scores** — relevance, faithfulness, hallucination scores with judge reasoning
  4. **Pass/Fail Summary** — tiered pass/fail (Classification → Response → Readiness) with per-metric breakdown
  5. **Reviewer Feedback** — full enterprise feedback controls (answerability, usability, bucket, safety, failure reasons, corrected response)

### Judge reasoning capture
- `rrScoreLLMMetric()` now returns `{score, reason}` instead of just a number
- Judge reasons stored in `details.judge_reasons` JSONB on each eval result (no schema migration needed — uses existing JSONB column)
- Judge Scores section in modal displays per-metric reasoning below each score
- Existing eval results without `judge_reasons` degrade gracefully (scores shown, reasoning omitted)

### Feedback auto-save on eval results
- Feedback in the detail modal auto-saves on click to DB via new `PATCH /api/eval/results/{id}` endpoint
- New `EvalResultUpdate` Pydantic model for partial result updates
- New `updateEvalResult()` method in `apiClient.js`
- No more manual save button — each feedback click persists immediately

---

## Session: 2026-03-22 (Feedback UX Improvements)

### Fix: Feedback bar on conversational (non-JSON) response cards
- **Problem:** When the LLM returned plain text (e.g. "Hello!") instead of structured JSON, `parsedJson` was null and `styleAssessmentResponse()` was skipped entirely — no feedback bar appeared.
- **Fix:** Added `else` branch after the `if (parsedJson)` block in `sendWorkbenchMessage()` that calls `buildInlineFeedback(assistantDiv)` so all response cards get feedback controls.
- **File:** `v2/static/js/page-workbench.js`

### Feature: Green "Reviewed" badge on cards with feedback
- **Problem:** After rating a card, there was no visual indicator that feedback had been given — hard to scan which cards were reviewed.
- **Fix:** In `_persistFeedback()`, after feedback is collected, a green `✓ FULL · Send as-is` badge is added/updated at the top-right of the card. Shows answerability + usability selections. Never duplicates.
- **File:** `v2/static/js/page-workbench.js`

---

## Session: 2026-03-21 (Voice Profile UX Simplification)

### Fix: Multi-turn conversation history uses draft_response instead of raw JSON
- In `sendWorkbenchMessage()`, assistant messages pushed to `workbenchMessages` now use `parsedJson.draft_response` (the natural language reply) instead of the full raw JSON eval output
- Falls back to raw `fullResponse` if JSON parsing fails or no `draft_response` field
- Raw JSON still preserved in trace (`rawResponse`), assessment context (`fullResponse`), and conversation API persistence
- Moved JSON parsing before the `workbenchMessages.push()` call so `draft_response` is available

### Sidebar cleanup: remove file uploads and data status bar
- Removed "Required Files" and "Optional Files" sections from sidebar (7 file upload inputs + "Load All Files" bulk upload)
- Removed data status bar (`dataStatusBar` with Classification/Validation/Taxonomy/Property pills) from page header
- Sidebar is now navigation-only: page links with icons and subtitles
- All file upload/import functionality remains on Settings page (server-side file import)
- Sidebar JS handlers are guarded with `if (el)` checks — no crashes from missing elements

### Judge Model for eval scoring
- Added separate "Judge Model" row to eval runs UI with Backend dropdown, Model select, Connect button
- Labeled existing controls as "Generation" and new ones as "Judge"
- `rrConnectJudge()` populates judge model dropdown independently
- `_getJudgeConfig()` helper returns effective judge model/backend, falling back to generation model
- `runEvaluation()` passes judge model to `rrScoreLLMMetric()` for relevance/faithfulness/hallucination scoring
- Judge model/backend stored in `config_snapshot` (`judge_model`, `judge_backend`, `judge_is_separate`)
- Warning shown during eval run when judge = generation model: "Judge = generation model"
- Run summary displays judge model info in status label

### Multi-intent feedback placement + bucket search in eval + docs
- "Detected intents correct?" always visible in Advanced section (all messages), ALSO shown in main feedback row when `is_multi_intent: true`
- Workbench main row: shows purple "Intents? Y/N" inline when multi-intent
- Eval sticky panel main row: shows purple "Multi-intent: Y/N" inline when multi-intent
- Eval detail modal: same treatment
- Eval sticky panel bucket "Wrong": shows inline suggested bucket input with datalist autocomplete from `window.taxonomyLookup`
- `saveDetailFeedback()` now collects `fb_suggested_bucket` from the inline input
- Updated inline results table dropdown: Good/Needs work/Hallucinated → Send as-is/Minor edit/Major rewrite/Discard
- Updated WORKBENCH-GUIDE.md: added Classification Feedback, Bucket Feedback, and multi-intent behavior sections

### Eval sticky feedback panel — enterprise controls
- Rebuilt `renderDetailFeedback()` with new enterprise controls matching workbench cards
- Row 1: Answerability (FULL/PARTIAL/NONE) + Usability (Send as-is/Minor edit/Major rewrite/Discard) + Bucket (Correct/Wrong) + Safe? (Y/N)
- Expandable section (shown when minor_edit+): failure reason checkboxes (8 reasons), hallucination severity toggle (Minor/Major), corrected response textarea pre-filled with draft_response
- Collapsible "Advanced" section: Confidence correct? (Y/N), Intents correct? (Y/N), Missing intents input
- `saveDetailFeedback()` now collects all new fields (failure reasons, corrected response, hallucination severity, classification feedback, reviewer ID, timestamp) and sends to API
- Updated results table inline dropdown: Good/Needs work/Hallucinated → Send as-is/Minor edit/Major rewrite/Discard
- Summary strip: added Send-as-is rate (%) and Safe-to-send rate (%) after Reviewed count

### Enterprise Feedback System Redesign
- **Response usability**: Replaced Good/Needs work/Hallucinated with four-tier scale: Send as-is, Minor edit, Major rewrite, Discard
- **Failure reasons**: Multi-select checkboxes (8 reasons) shown when minor_edit+ selected. Stored as `fb_failure_reasons` JSONB array
- **Corrected response**: Textarea pre-filled with draft_response, stored as `fb_corrected_response`
- **Hallucination severity**: Minor/Major toggle when "Hallucinated facts" checked, stored as `fb_hallucination_severity`
- **Deflection safety**: Always-visible "Safe to auto-send?" Y/N toggle, stored as `fb_safe_to_send` BOOLEAN
- **Reviewer tracking**: `fb_reviewer_id` auto-stamped from Settings page "Reviewer name" (localStorage). `fb_timestamp` recorded on feedback
- **DB schema**: Added 10 new columns to workbench_assessments DDL + migration block for existing DBs
- **Pydantic models**: All new fields added to WorkbenchAssessmentCreate and WorkbenchAssessmentUpdate
- **Router**: `_COLS` and `_JSONB_COLS` updated, `fb_timestamp` conversion added alongside `timestamp`
- **Workbench UI**: Rebuilt `buildInlineFeedback()` with compact button row + expandable corrections section. Added `_collectFeedbackFromBar()` and `_persistFeedback()` helpers
- **Eval detail pane**: Replaced alert() with proper modal with scores grid, draft response, and feedback controls
- **Settings page**: Added "Reviewer Settings" card with name input, save button, localStorage persistence, global `getReviewerName()` accessor
- **Documentation**: Updated WORKBENCH-GUIDE.md section 5 with new scale definitions, failure taxonomy, deflection safety, reviewer tracking, analytics definitions

### EV-04: BucketMatch false positive fix in comparison view
- Fixed `bucket_seems_correct !== false` → `=== true` in comparison table display (lines 2032-2033)
- Main scoring logic was already fixed; this catches the remaining instance in `showEvalComparison`

### EV-03: Intent-specific coverage scoring
- Replaced `parseFloat(meta.coveragePct || 0) / 100` (total property field coverage) with intent-specific calculation
- Now reads `window.marshaMapping[bucket].fields` for the test case's intent, checks which of those mapped fields exist in `window.propCatalogMap[propertyCode]`, computes `fields_present / fields_mapped`
- A property with 95% total coverage but 0% of the parking-related fields now correctly scores 0 for a parking question
- Unmapped buckets (no MARSHA mapping) score 0 coverage

### EV-01 + EV-08: LLM-as-judge rubrics
- Replaced vague "rate 0.0 to 1.0" prompts in `rrScoreLLMMetric()` with explicit scoring rubrics
- **Relevance**: 5-point rubric (1.0 direct answer → 0.0 off-topic)
- **Faithfulness**: 4-point rubric anchored to property data verification (1.0 all claims supported → 0.0 invented facts); general statements without claims default to 0.8
- **Hallucination**: 4-point rubric (0.0 no hallucination → 1.0 severe fabrication)
- All prompts now require JSON response `{"score": <number>, "reason": "<brief>"}`
- Property data context (`groundingCtx`) appears after the rubric text for faithfulness/hallucination

### Fix: System prompt rebuild + trace accuracy in multi-turn mode
- Fixed stale system prompt bug: in multi-turn mode, `workbenchMessages[0]` (the system message) is now rebuilt on every turn, so changing property code or intent mid-conversation takes effect immediately
- Previously the system prompt was only set on the first message; subsequent turns reused the frozen turn-1 prompt
- Trace panel conversation context now shows richer breakdown: "System prompt (rebuilt each turn) + N guest + N agent messages" with total payload count
- Single-turn trace shows total message count sent to LLM

### System Prompt: Capabilities Section + Conversational Fallback + Trace Context
- Added `buildCapabilitiesSection()` to `llm.js` — auto-generates CAPABILITIES section from `window.taxonomyLookup`, grouping buckets by category into RAG-answerable vs handoff-to-human lists
- Capabilities section injected between DATA and RULES in `buildSystemPrompt()` (both `llm.js` and `page-workbench.js`)
- Added capabilities rule: LLM uses CAPABILITIES list to answer "what can you help with?" instead of returning NONE
- Added conversational fallback rule to system prompt via `- CONVERSATIONAL STYLE:` line, injected alongside `- VOICE:`
- Default warm fallback text hardcoded in `_defaultConversationalFallback` — editable in Voice Profile modal via new "Conversational Style" textarea with Warm Default / Formal / Playful presets
- Conversational fallback persisted in wbSettings and saved profiles
- Added "Conversation Context" section to trace panel — shows message count and summary of all user/assistant messages in the payload
- All three trace creation sites (single send, multi-message case, batch) now include `conversationMessages` and `chatMode` in trace object
- Single-turn mode shows "Single-turn mode — no prior context sent"; conv mode shows numbered message list with role labels

### Security Fixes (S-01 + S-02)
- Removed hardcoded API key `sk-3ZK6...` from workbench.html template — field now starts empty
- API key served from server via `/api/config/frontend` endpoint (reads `LITELLM_API_KEY` env var)
- Frontend `llm.js` auto-populates the API key field from server config if user hasn't entered one manually
- User-saved key in IndexedDB still takes priority via `restoreWbSettings()`
- Updated `.gitignore`: added `.env`, `creds.txt`, `__pycache__/`, `node_modules/`, `.DS_Store`, `*.sqlite`, `*.db`, IDE dirs

### Conversation History Fixes
- Fixed duplicate conversation entries: single-turn mode with same case ID now reuses existing conversation instead of creating a new one each send
- Fixed conversation labels: now uses the user's message text instead of raw case ID (falls back to case ID only if no message)
- Fixed conversation preview line: shows property code, case ID (truncated), and intent as secondary metadata instead of duplicating the label
- Removed dead MARSHA mapping HTML from config modal (was hidden, already moved to Product Catalog page)

### Voice Profile (was Brand Voice)
- Merged three separate fields (Tone, Persona, Custom Guidelines) into a single **Voice Instructions** freeform textarea
- Renamed "Brand Voice Settings" → "Voice Profile", "Prompt Versions" → "Saved Profiles"
- Presets now fill the single textarea with complete voice descriptions (combined tone + persona)
- Sidebar trigger and response card badges now show the active profile name (or "Custom"/"Default")
- `getBrandVoicePrompt()` returns single `- VOICE:` line instead of separate TONE/PERSONA/BRAND GUIDELINES
- `_getBrandVoiceLabel()` returns active profile name instead of `getToneLabel() / getPersonaLabel()`
- Backward compatibility: old settings with `brandTone`/`brandPersona`/`brandGuidelines` auto-migrate on load
- Old prompt versions with separate tone/persona/guidelines fields merge on load via `loadPromptVersion()`
- Removed: `getToneLabel()`, `getPersonaLabel()`, `_tonePresets`, `_personaPresets`
- Updated `llm.js` `getBrandVoicePrompt()` to match
- Updated WORKBENCH-GUIDE.md with new Voice Profile documentation

## Session: 2026-03-21

### Eval Tiered Pass/Fail
- Split monolithic pass/fail into three tiers: Classification → Response → Readiness
  - **Classification pass**: ansMatch ≥ 1.0, bucketMatch ≥ 0.5, ambiguityMatch ≥ 1.0
  - **Response pass**: classification pass + relevance, faithfulness, hallucination thresholds
  - **Readiness pass** (full): response pass + coverage ≥ threshold + latency
- Each result now stores `classificationPass`, `responsePass`, `pass`
- `computeRunSummary()` reports all three pass rates
- Summary cards show Classification / Response / Readiness rates with tooltips
- Results table shows tiered badges: READY (green), RESP (blue), CLASS (orange), FAIL (red)
- Filter dropdown supports filtering by each tier
- Fixed `bucketMatch` false positive: `parsed.bucket_seems_correct !== false` → `=== true`

### Bug Fixes
- Fixed eval run save 500: parse ISO timestamp string to datetime before asyncpg insert
- Fixed workbench property/intent state persisting from batch runs on refresh

## Session: 2026-03-20

### Sidebar Redesign
- Rewrote sidebar into two-zone layout (Conversations + Case Browser) with draggable divider
- Replaced 6-column table with grouped case cards showing case ID, property, bucket badges, message rows
- Added server-side case search endpoint (`GET /api/classification/search`)
- Added server-side case messages endpoint (`GET /api/classification/case/{id}`)
- Added server-side property code lookup (`GET /api/prop-catalog/code-map/{case_id}`)
- Filters (Intent, Route, RAG Mode) populate from taxonomy data — no bulk download
- Require at least one filter to search; results capped at 500
- Assessed messages shown with colored dots; fully assessed cases dimmed
- Single message click auto-sends through LLM
- "Full Case" button runs all messages sequentially via server-side fetch

### Batch Modal + Server-Side Batch
- Moved batch filters into modal overlay
- Batch modal opens instantly — no data download
- Live match count via server-side `GET /api/classification/match-count`
- Random case selection via server-side `GET /api/classification/random-cases`
- Fixed `populateRandomPropFilter` O(n²) innerHTML freeze (8,574 property codes)
- `runRandomCases` no longer downloads classification data — fully server-side

### Response Cards Redesigned
- Compact header with colored answerability pill, route tags, override badge, brand voice label, timestamp
- Override indicator: yellow badge with shuffle icon on both BOT and HANDOFF cards
- Brand voice shown on all card types
- Timestamps on guest messages and bot responses
- Fixed handoff card HTML entity bug (`textContent` → `innerHTML` for lightbulb icon)
- Fixed "Assessment Details" click hijacked by trace handler

### Feedback System
- Auto-save to eval on first answerability click (removed "Push to Eval" button)
- Feedback icons (thumbs-up, comment-dots) on feedback bar
- Feedback persisted to conversation messages via `PATCH /api/conversations/messages/{id}/feedback`
- Fixed double-JSON-encoding bug (removed `json.dumps` from conversations router — asyncpg codec handles it)
- Fixed `Body(...)` annotation for PATCH endpoint
- Feedback restored on conversation reload with button highlights + eval indicator

### Assessment Pipeline to Postgres
- All 4 assessment creation paths now save to Postgres via `apiClient.saveAssessment()`
- Shared `_buildAssessment()` helper centralizes field construction
- New fields captured: response_time_ms, response_length, input/output_tokens, taxonomy_category, taxonomy_route, brand_voice_tone, brand_voice_persona, conversation_id, route_override, system_prompt, raw_llm_response
- DB schema + Pydantic models + router updated for new columns with migration
- `ensureAssessmentData()` hydrates from Postgres, falls back to IndexedDB
- Eval page `loadFromWorkbench()` reads from Postgres API
- Eval page feedback (`saveRrFeedback`) saves to Postgres
- Removed all `dataStore.setCached('workbenchAssessments', ...)` calls

### Conversation Persistence
- Added `feedback` JSONB column to `workbench_messages` table with migration
- Messages saved with `await` so `_msgId` is set before user can click feedback
- Old conversations restore parsed JSON from raw content if `parsed_response` missing
- Fixed handoff card class selector for message ID mapping

### Nav & Branding
- Updated 7 nav subtitles (quality, rag, validation, propcat, taxonomy, workbench, ragresults)
- Marriott SVG logo: full logo when nav expanded, flame icon when collapsed
- Moved FastAPI OpenAPI docs to `/api/openapi` to free `/docs` path

### Docs Page
- Created dedicated `/docs` page with sidebar TOC, styled content area, Mermaid diagram support
- Wrote comprehensive WORKBENCH-GUIDE.md with 10 sections + Mermaid flowcharts
- All docs cross-referenced (Architecture, API Routes, Security Audit, Recommendations)
- Converted ASCII diagrams in ARCHITECTURE.md to Mermaid
- Fixed Mermaid renderer (extract code blocks before HTML escaping)
- Added `GET /api/docs` and `GET /api/docs/{name}` endpoints

### Eval Page (Delete)
- Added "Clear All" button with confirmation
- Added per-row delete button in expanded detail
- Delete calls `apiClient.deleteAssessment(id)` + re-renders

### Database
- Added indexes: `idx_cls_role`, `idx_cls_role_bucket` (partial) on classification_rows
- Added `feedback` column to workbench_messages with migration
- Added 12 new columns to workbench_assessments with migration
- Fixed settings router: null value now deletes key instead of crashing

### Eval Pipeline Fixes (E-07, E-08, E-09)
- Test case lineage: `source_assessment_id` field traces test cases back to source assessment (DB schema + Pydantic + router + JS)
- Prompt version tracking: eval runs capture active brand voice config (tone, persona, guidelines) in `config_snapshot` and `prompt_version`
- LLM-as-judge faithfulness + hallucination scoring now includes product catalog data as grounding context (relevance left as-is)
- Eval page Save button: added warning when assessment has no Postgres ID (CSV imports)

### Mobile
- Added 44px min-height touch targets at max-width 768px

### Routing
- Override detection now checks `window.routingRules` (not just `INTENT_OVERRIDE_RULES`)
- `route_override` boolean saved in all assessment creation paths
