# Pytest Failure Analysis

> Harness CI · Pipeline 1402 · Python 3.10.18 · pytest 8.4.2 · Apr 18 2026 04:31 UTC

---

## Summary

| Status  | Count |
|---------|------:|
| Total   | 396   |
| Passed  | 362   |
| Failed  | 29    |
| Skipped | 5     |
| Pass Rate | 91% |

---

## Root Cause Summary

All 29 failures trace back to **two distinct root causes**. Fixing them requires changes to `requirements.txt` and one test fixture — no production code changes needed.

### Root Cause 1 — Missing `pytest-asyncio` (28 failures)

Both `test_classification_import.py` and `test_workbench_batch.py` use `@pytest.mark.asyncio` and `async def` test functions, but `pytest-asyncio` is **not listed in `requirements.txt`**. The CI install script only adds `pytest pytest-cov coverage`, so the plugin never gets installed.

**Symptoms:**
- `async def functions are not natively supported`
- `PytestUnknownMarkWarning: Unknown pytest.mark.asyncio`
- `PytestConfigWarning: Unknown config option: asyncio_mode`

### Root Cause 2 — Redirect Loop on Root Route (1 failure)

`test_root_dashboard_html` calls `client.get("/")` which triggers an OAuth/auth redirect chain. httpx follows redirects by default (max 20) and the auth loop never resolves — bouncing between `302 → 302 → 307 → 302 → 307 …` until it crashes.

**Symptom:** `httpx.TooManyRedirects: Exceeded maximum allowed redirects`

---

## Required Fixes

| Issue | Affected File(s) | Priority | Fix |
|-------|-----------------|----------|-----|
| `pytest-asyncio` not installed | `test_classification_import.py`, `test_workbench_batch.py` | **High** | Add `pytest-asyncio>=0.23` to `requirements.txt`; add `asyncio_mode = "auto"` to `pyproject.toml` |
| `asyncio_mode` config unrecognised | All files (PytestConfigWarning) | **High** | Resolved once `pytest-asyncio` is installed — the key becomes valid |
| Redirect loop on `GET /` | `test_main_generated.py` | **Medium** | Override auth dependency in test fixture or disable `follow_redirects` in `TestClient` |
| Module `app` never imported (coverage) | coverage warning | Low | Pass `--cov=src` or correct `PYTHONPATH` so coverage resolves the `app` module |

---

## Failure Details by File

### `test_classification_import.py` — 11 failed

Error: `async def functions are not natively supported`

| Test |
|------|
| `TestImportFromPathAllowed::test_basic_csv_returns_inserted_count` |
| `TestImportFromPathAllowed::test_tsv_file_uses_tab_delimiter` |
| `TestImportFromPathAllowed::test_multiple_rows_all_inserted` |
| `TestImportFromPathAllowed::test_shifted_row_is_detected_and_corrected` |
| `TestImportFromPathAllowed::test_non_integer_message_index_becomes_none` |
| `TestImportFromPathAllowed::test_path_in_subdirectory_of_allowed_dir` |
| `TestImportFromPathTraversalBlocked::test_absolute_path_outside_allowed_dir_is_rejected` |
| `TestImportFromPathTraversalBlocked::test_traversal_via_dotdot_is_rejected` |
| `TestImportFromPathTraversalBlocked::test_empty_allowed_dirs_rejects_all_paths` |
| `TestImportFromPathTraversalBlocked::test_path_that_is_a_prefix_but_not_subdir_is_rejected` |
| `TestImportFromPathTraversalBlocked::test_nonexistent_file_inside_allowed_dir_returns_400` |

---

### `test_workbench_batch.py` — 17 failed

Error: `async def functions are not natively supported`

| Test |
|------|
| `TestLoadCaches::test_empty_db` |
| `TestLoadCaches::test_taxonomy_rows_indexed_by_bucket_key` |
| `TestLoadCaches::test_mapping_rows_indexed_by_bucket_key` |
| `TestLoadCaches::test_mapping_null_fields_becomes_empty_list` |
| `TestLoadCaches::test_prop_cache_always_empty_initially` |
| `TestEnsurePropertyCached::test_skips_when_already_cached` |
| `TestEnsurePropertyCached::test_skips_empty_marsha` |
| `TestEnsurePropertyCached::test_fetches_and_parses_json_string` |
| `TestEnsurePropertyCached::test_fetches_dict_fields_directly` |
| `TestEnsurePropertyCached::test_sets_empty_dict_when_not_found` |
| `TestProcessMessage::test_result_keys_present` |
| `TestProcessMessage::test_conversation_history_grows` |
| `TestProcessMessage::test_taxonomy_fields_applied_to_result` |
| `TestProcessMessage::test_unparseable_llm_response_sets_error` |
| `TestProcessMessage::test_db_execute_called_once` |
| `TestProcessMessage::test_system_prompt_truncated_in_result` |
| `TestProcessMessage::test_chat_mode_single_vs_conversation` |

---

### `test_main_generated.py` — 1 failed

Error: `httpx.TooManyRedirects: Exceeded maximum allowed redirects`

| Test |
|------|
| `test_root_dashboard_html` |

---

## Test Scenario Change Suggestions

| Scope | Suggested Change | Notes |
|-------|-----------------|-------|
| `test_classification_import.py` (all 11) | Plugin fix unblocks all. Consider also adding `anyio` fixtures for broader backend compatibility. | Already marked with `@pytest.mark.asyncio` — just needs the plugin |
| `test_workbench_batch.py` (all 17) | Same async plugin issue. After fix, review `TestLoadCaches` — may need a real or in-memory `asyncpg` pool fixture if secondary failures appear. | Watch for secondary failures post-fix |
| `test_main_generated.py::test_root_dashboard_html` | Inject a mock authenticated user via `dependency_overrides`, or call `TestClient(app, follow_redirects=False)` and assert `status_code == 302` rather than asserting HTML. | Fundamental design change needed |
| `test_live_integration.py` (4 skipped) | Already correctly skipped. Confirm they have `@pytest.mark.integration` and CI uses `-m "not integration"` to exclude them. | No change needed — correct pattern |
| `test_regression_live.py` (1 skipped) | Same as above — verify skip marker is intentional (live endpoint dependency). | Verify skip marker is correct |

---

## Immediate Action Plan

**Step 1 — Add to `requirements.txt`:**

```
pytest-asyncio>=0.23
```

**Step 2 — Add to `pyproject.toml`** under `[tool.pytest.ini_options]`:

```toml
asyncio_mode = "auto"
```

**Step 3 — Fix `test_root_dashboard_html`:**

Option A — override auth dependency:
```python
from app.dependencies import get_current_user

app.dependency_overrides[get_current_user] = lambda: {"user": "test"}

def test_root_dashboard_html(client: TestClient):
    r = client.get("/")
    assert r.status_code == 200
```

Option B — don't follow redirects, assert 302:
```python
def test_root_dashboard_html():
    client = TestClient(app, follow_redirects=False)
    r = client.get("/")
    assert r.status_code in (302, 307)
```

**Step 4 — Fix coverage path:**

Change the pytest command from:
```
pytest --cov=app tests/
```
to:
```
pytest --cov=src tests/
```
or ensure `PYTHONPATH` includes the directory where the `app` module lives.

---

> 362 tests pass cleanly. No regressions in `test_assessment_pipeline`, `test_followup`, `test_message_quality_filter`, or `test_rbac`.
