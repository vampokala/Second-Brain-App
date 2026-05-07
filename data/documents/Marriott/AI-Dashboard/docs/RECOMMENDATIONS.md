# Marriott AI Dashboard — Prioritized Recommendations

> Remediation roadmap addressing findings from the [Security Audit](SECURITY-AUDIT.md).
>
> **Related docs:** [Architecture](ARCHITECTURE.md) | [API Routes](API-ROUTES.md) | [Workbench Guide](WORKBENCH-GUIDE.md)

## Priority Legend

- **P0** — Fix immediately, blocks production readiness
- **P1** — Fix before any broader deployment
- **P2** — Fix during next development cycle
- **P3** — Improve when capacity allows

---

## Immediate / Quick Fixes (< 1 day each)

| # | Priority | Action | Addresses | File(s) |
|---|----------|--------|-----------|---------|
| 1 | **P0** | **Create `.gitignore`** — add `.env`, `creds.txt`, `__pycache__/`, `*.pyc`, `node_modules/` | C2, C3 | `.gitignore` (new) |
| 2 | **P0** | **Remove hardcoded API key from HTML** — change `value="sk-3ZK6..."` to `value=""` in workbench template | C1 | `v2/templates/pages/workbench.html:239` |
| 3 | **P0** | **Delete `creds.txt`** — credentials must only live in `.env` | C3 | `v2/creds.txt` |
| 4 | **P0** | **Remove default password from config.py** — use `os.environ["DB_PASSWORD"]` (fail if unset) | H7 | `v2/config.py:22` |
| 5 | **P1** | **Rotate the exposed API key** — `sk-3ZK6ZOwb0GPsFcDjbdLPfg` has been in HTML source and .env; assume compromised | C1 | External (Marriott TIP-AI admin) |
| 6 | **P1** | **Fix CORS** — replace `["*"]` with specific origins (e.g., `["http://localhost:9505"]`) | H1 | `v2/app.py:51` |
| 7 | **P1** | **Fix XSS in `loadConversation()`** — change `div.innerHTML = msg.content.replace(/\n/g, '<br>')` to `div.textContent = msg.content` with CSS `white-space: pre-wrap` | H3 | `v2/static/js/page-workbench.js:162` |
| 8 | **P1** | **Fix XSS in `restoreConversationState()`** — sanitize or use `textContent` instead of `area.innerHTML = state.html` | H4 | `v2/static/js/page-workbench.js:748` |
| 9 | **P1** | **Fix route shadowing** — move `/{key}` route definition below `/routing-rules` and `/aggregations` | M2 | `v2/routers/settings.py` |
| 10 | **P2** | **Add upper bound to `limit` params** — add `le=10000` to all Query limit parameters | M8 | `classification.py`, `validation.py`, `prop_profile.py`, `workbench.py` |
| 11 | **P2** | **Use `escapeHtml()` in page-settings.js** — escape `err.message` and system info values before innerHTML | L6, L7 | `v2/static/js/page-settings.js:83,125,206,238` |
| 12 | **P2** | **Use `escapeHtml()` consistently in styleAssessmentResponse** — replace `.replace(/</g, '&lt;')` with `escapeHtml()` | M5 | `v2/static/js/page-workbench.js:1421` |
| 13 | **P2** | **Remove dead code** — delete or implement `buildInlineFeedback()` | L5 | `v2/static/js/page-workbench.js:1483` |

---

## Moderate Effort (1-3 days each)

| # | Priority | Action | Addresses | Details |
|---|----------|--------|-----------|---------|
| 14 | **P0** | **Add authentication middleware** | C4 | At minimum, API key validation via `X-API-Key` header or `Authorization: Bearer`. For Marriott internal, integrate with corporate SSO/SAML. Apply to all routes except `/health`. |
| 15 | **P1** | **Remove or restrict `import-file` endpoint** | C5 | Either delete `POST /api/classification/import-file` entirely, or add an allowlisted directory check: validate that `os.path.realpath(path)` starts with a configured `DATA_IMPORT_DIR` env var. |
| 16 | **DONE** | **Proxy LLM calls through backend** | H2, H5 | Implemented in `routers/llm_proxy.py`: `/api/llm/chat` (streaming), `/api/llm/chat/sync`, `/api/llm/models`, `/api/llm/config`. API keys stay server-side. Frontend uses `callLLM()`, `callLLMSync()`, `fetchModels()`. |
| 17 | **P1** | **Add pagination to unbounded endpoints** | M7 | Add `limit` and `offset` params to `GET /api/workbench/assessments/export` and `GET /api/validation/enriched`. Or use streaming JSON responses. |
| 18 | **P2** | **Replace f-string SQL with allowlists** | M1 | Add explicit assertions before every f-string SQL interpolation. Example: `assert t in ALLOWED_TABLES, f"Invalid table: {t}"` |
| 19 | **P2** | **Add request logging middleware** | L1 | Log method, path, status code, duration, source IP, and user identity (once auth exists) to structured logs or a database table. |
| 20 | **P2** | **Add health check endpoint** | L8 | `GET /health` that checks DB connectivity and returns `{"status": "ok", "db": "connected", "version": "2.0"}`. |
| 21 | **P2** | **Add Pydantic models for feedback endpoints** | L2 | Define `TaxonomyFeedback` and `MessageFeedback` Pydantic models to validate the feedback body shape. |
| 22 | **P2** | **Encrypt API keys in settings storage** | H2 | Use Fernet symmetric encryption (from `cryptography` package) to encrypt API keys before storing in the `settings` JSONB. Decrypt on read. |

---

## Significant Effort (3+ days)

| # | Priority | Action | Addresses | Details |
|---|----------|--------|-----------|---------|
| 23 | **P1** | **Implement RBAC (Role-Based Access Control)** | C4, H6 | Define roles: `viewer` (read-only), `analyst` (read + write), `admin` (read + write + delete + settings). Apply role checks to destructive operations. |
| 24 | **P2** | **Add rate limiting** | M3 | Use `slowapi` or custom middleware. Suggested limits: 10 req/min for `/api/aggregations/compute`, 100 req/min for write endpoints, 1000 req/min for read endpoints. |
| 25 | **P2** | **Implement PII handling** | Multiple | Data retention policies (auto-purge guest messages after N days), access logging for PII endpoints, encryption at rest for `message_text` fields, data masking for non-admin roles. |
| 26 | **P3** | **Production deployment hardening** | Multiple | Disable `--reload`, set `ENV_NAME=production`, use `gunicorn` with multiple workers, configure TLS termination via reverse proxy, use secrets manager for credentials (e.g., AWS Secrets Manager, Azure Key Vault), add Dockerfile and `requirements.txt`. |
| 27 | **P3** | **Create dependency manifest** | Infrastructure | Create `requirements.txt` or `pyproject.toml` with pinned versions. Current dependencies (from imports): `fastapi`, `uvicorn`, `asyncpg`, `python-dotenv`, `starlette`. |
| 28 | **P3** | **Disable migration endpoint in production** | Multiple | `POST /api/migrate/from-indexeddb` can bulk-write to every table. Either remove it or gate it behind `ENV_NAME == "development"` check. |

---

## Recommended Implementation Order

### Phase 1: Stop the Bleeding (Week 1)
1. Create `.gitignore` (#1)
2. Remove hardcoded API key from HTML (#2)
3. Delete `creds.txt` (#3)
4. Rotate the exposed API key (#5)
5. Fix CORS (#6)
6. Fix XSS vulnerabilities (#7, #8)
7. Fix route shadowing (#9)

### Phase 2: Core Security (Weeks 2-3)
8. Add authentication middleware (#14)
9. Remove/restrict import-file endpoint (#15)
10. Proxy LLM calls through backend (#16)
11. Add rate limiting (#24)
12. Add request logging (#19)

### Phase 3: Hardening (Weeks 4-6)
13. Implement RBAC (#23)
14. Add pagination to unbounded endpoints (#17)
15. Implement PII handling (#25)
16. Production deployment hardening (#26)

### Phase 4: Polish (Ongoing)
17. Replace f-string SQL patterns (#18)
18. Add health check (#20)
19. Pydantic models for feedback (#21)
20. Create dependency manifest (#27)

---

## Code Quality Notes

### Eval Framework Status
Fully implemented and functional. Test cases CRUD, run management with cascading
results, bulk import, and run comparison all work correctly with proper Pydantic
validation.

### dataStore.js Caching
- Simple in-memory cache with no TTL or eviction
- Cross-tab invalidation via BroadcastChannel (good)
- Cache-then-network pattern: serves stale data until explicitly invalidated
- No cache size limits — could grow to hundreds of MB on large datasets
- `pagehide` listener properly nulls globals and clears cache (good OOM prevention)

### Batch Processing Race Conditions
`runRandomCases` in `page-workbench.js` has reasonable mitigations:
- AbortController signal checked before each case and message
- `workbenchStreaming` flag prevents concurrent sends
- DOM nodes trimmed to 200 elements during batch runs
- Batch state saved for resume capability

Minor risk: `saveWbBatchState()` async persistence could be inconsistent on page crash,
but acceptable for a development tool.

### Connection Pool Sizing
`min=2, max=10` is appropriate for single-user or small-team use. For concurrent
multi-user access, increase `max` to 20-25 and monitor connection wait times.

### Error Handling Patterns
- Backend: lets database exceptions propagate as HTTP 500 (adequate for internal tool)
- Frontend: `dataStore` silently swallows errors (problematic for debugging)
- `llm.js`: SSE parser silently skips malformed lines (acceptable)
- No global `window.onerror` or `unhandledrejection` handler

### migrate.py Assessment
One-time migration endpoint for moving data from browser IndexedDB (v1) to PostgreSQL
(v2). Uses `ON CONFLICT DO NOTHING` for safety. Should be disabled or removed after
migration is complete, as it can bulk-insert data into every table without auth.
