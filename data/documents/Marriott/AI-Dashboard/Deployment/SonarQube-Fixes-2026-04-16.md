# SonarQube Security Fixes — AI Dashboard

**Date:** 2026-04-16  
**Branch:** `feature/react-ui`  
**Scope:** Security vulnerability remediation across backend API and frontend JS

---

## Summary

This change set resolves multiple SonarQube-flagged vulnerabilities (CWE-22 Path Traversal, ReDoS, hardcoded message strings, and cognitive complexity) across the ECMP Dashboard backend and frontend.

---

## Changes by File

### 1. `src/adapters/inbound/routers/classification.py`

**Vulnerability fixed:** CWE-22 — Path Traversal  
**SonarQube rule:** `python:S2083`

| Before | After |
|---|---|
| `path` query param passed directly to `open()` | Resolved via `Path(path).resolve()` |
| No directory restriction | Validated against `_ALLOWED_IMPORT_DIRS` allowlist |
| `str.startswith()` string prefix check | `Path.is_relative_to()` — proper path containment |

**Root cause:** The `/api/classification/import-file` endpoint accepted an arbitrary filesystem path via query parameter and opened it directly, allowing an attacker to read any file accessible to the server process (e.g., `../../etc/passwd`).

**Fix details:**
- `Path(path).resolve()` canonicalises the path, collapsing all `../` traversal sequences and symlinks
- Resolved path is validated against `_ALLOWED_IMPORT_DIRS` (env var `IMPORT_ALLOWED_DIRS`, default `/data/imports,/tmp`) using `Path.is_relative_to()` — a true path containment check, not a string prefix match
- File is opened via the resolved `Path` object, never the raw user-supplied string
- `from pathlib import Path` moved to top-level imports (no-inline-imports rule)

**New test file:** `tests/test_classification_import.py` — 15 tests:
- 6 positive scenarios (valid allowed-dir paths, TSV, multi-row, shifted-row detection, bad message_index, subdirectory)
- 5 negative/traversal scenarios (outside allowed dir, `../../` traversal, empty allowlist, string-prefix bypass, file not found)
- 4 unit tests for `_fix_shifted_row`

---

### 2. `src/adapters/inbound/web/static/js/llm.js`

**Vulnerability fixed:** ReDoS — Regular Expression Denial of Service  
**SonarQube rule:** `javascript:S5852`

| Before | After |
|---|---|
| `result.match(/\{[\s\S]*?\}/)` — backtracking regex on untrusted LLM output | `indexOf('{')` + `lastIndexOf('}')` — O(n), no backtracking |
| `"score"\s*:\s*(\d)` — unbounded whitespace quantifiers | `"score"\s{0,10}:\s{0,10}(\d)` — bounded quantifiers |

**Root cause:** `judgeResponse()` parsed JSON from LLM output using `[\s\S]*?` which triggers super-linear backtracking on crafted input, enabling CPU exhaustion.

---

### 3. `src/adapters/inbound/auth.py`

**Issue:** Cognitive complexity — `python:S3776`

Extracted two helper functions from `AuthMiddleware.dispatch()`:
- `_unauthenticated_response(path, message)` — centralises HTML-redirect vs JSON-401 branching
- `_check_permission(method, path, cached)` — centralises page-route / API-route RBAC check

No behaviour change; complexity reduced for maintainability and testability.

---

### 4. `src/adapters/inbound/routers/assessment_pipeline.py`

**Issues addressed:**
- **Duplicated string literals** — `"Run not found"` repeated 4× → extracted to `_RUN_NOT_FOUND` constant (`python:S1192`)
- **Cognitive complexity** in `get_results`, `export_csv`, `gap_report_run`, `_extract_cited_fields` (`python:S3776`)

**Extracted helpers:**

| Helper | Purpose |
|---|---|
| `_example_to_dict(ex)` | Maps DB row to API response dict |
| `_intent_row_to_dict(ir, tax_map, examples_map)` | Maps intent result row to API response dict |
| `_intent_row_to_csv_dict(prop, r)` | Maps intent row to CSV export dict |
| `_CSV_FIELDNAMES` constant | Single source of truth for CSV column list |
| `_accumulate_missing_field()` / `_accumulate_suggested_field()` | Field stats accumulation |
| `_gap_stats_to_dict()` | Gap report dict builder |
| `_deduplicate_ordered()` | Deduplicate list preserving insertion order |
| `_format_value()` | Truncate property value to 300 chars |
| `_resolve_ref_line()` | Annotate a single cited field reference |

**New test file:** `tests/test_assessment_pipeline.py` (886 lines) — comprehensive unit tests for all extracted helpers.

---

### 5. `src/adapters/inbound/routers/workbench.py`

**Issue:** `python:S1192` — `"Template not found"` repeated 5×  
→ Extracted to `_TEMPLATE_NOT_FOUND` constant

---

### 6. `src/adapters/inbound/routers/workbench_batch.py`

**Issue:** `python:S3776` — Cognitive complexity in `_run_batch()`

**Extracted helpers:**

| Helper | Purpose |
|---|---|
| `_load_caches(db)` | Loads taxonomy, mapping caches from DB |
| `_ensure_property_cached(db, prop_cache, marsha)` | Lazy-loads a single property into cache |
| `_build_llm_messages(system_prompt, history, message)` | Assembles LLM messages array |
| `_build_trace_blob(...)` | Serialises trace metadata to JSON string |
| `_process_message(...)` | Full LLM call + DB insert + result dict for one message |

**New test file:** `tests/test_workbench_batch.py` — unit tests for all extracted helpers.

---

### 7. `src/config/settings.py`

**Issue:** Incorrect SSL mode for asyncpg  
`_ssl_for_asyncpg()` was returning `True` for `require` mode, which causes asyncpg to call `ssl.create_default_context()` — this fails when the DB uses a private CA cert (e.g., AWS RDS).  
→ Now returns the string `"require"` so asyncpg encrypts without verifying the CA.

---

## Test Coverage Added

| Test File | Status | Tests |
|---|---|---|
| `tests/test_classification_import.py` | New (untracked) | 15 — path traversal +/-, `_fix_shifted_row` unit |
| `tests/test_assessment_pipeline.py` | New (staged) | 886 lines — all assessment helpers |
| `tests/test_workbench_batch.py` | New (staged) | All workbench_batch helpers |
| `tests/test_rbac.py` | Modified (staged) | Updated for refactored auth middleware |

---

## SonarQube Rules Addressed

| Rule ID | Category | File(s) |
|---|---|---|
| `python:S2083` | CWE-22 Path Traversal | `classification.py` |
| `javascript:S5852` | ReDoS | `llm.js` |
| `python:S3776` | Cognitive Complexity | `auth.py`, `assessment_pipeline.py`, `workbench_batch.py` |
| `python:S1192` | Duplicated String Literals | `assessment_pipeline.py`, `workbench.py` |

---

## Git Status

```
branch:     feature/react-ui
staged:     auth.py, assessment_pipeline.py, workbench.py,
            workbench_batch.py, llm.js, settings.py,
            tests/test_assessment_pipeline.py, tests/test_rbac.py,
            tests/test_workbench_batch.py
unstaged:   src/adapters/inbound/routers/classification.py
untracked:  tests/test_classification_import.py
```
