# Marriott AI Dashboard — API Route Inventory

> Complete endpoint reference for all 16 API routers.
>
> **Related docs:** [Architecture](ARCHITECTURE.md) | [Workbench Guide](WORKBENCH-GUIDE.md) | [Security Audit](SECURITY-AUDIT.md)

All routes are unauthenticated. No endpoints require any form of authentication.

---

## Core App Routes (`v2/app.py`)

| Method | Path | Handler | Purpose | Input Validation |
|--------|------|---------|---------|------------------|
| GET | `/api/config/frontend` | `frontend_config()` | Serve non-secret config to JS | N/A |
| GET | `/api/stats/row-counts` | `row_counts()` | Table row counts (all 16 tables) | N/A |
| GET | `/api/stats/system-info` | `system_info()` | PG version, Python version, platform | N/A |
| GET | `/` | `root()` | Redirect to `/exec` | N/A |
| GET | `/{page_id}` | `dashboard_page()` | Render page template | Allowlist validated |

---

## Classification Router (`/api/classification`) — `v2/routers/classification.py`

| Method | Path | Handler | Purpose | Input Validation |
|--------|------|---------|---------|------------------|
| GET | `/api/classification/search` | `search_rows()` | Server-side filtered search (case browser) | `q`, `bucket`, `route`, `rag_mode`, `limit` (max 500) |
| GET | `/api/classification/case/{case_id}` | `get_case_messages()` | All messages for a case | Path param |
| GET | `/api/classification` | `list_rows()` | List classification rows | `limit: int (ge=1, no max)`, `offset: int (ge=0)` |
| GET | `/api/classification/count` | `row_count()` | Row count | N/A |
| POST | `/api/classification/bulk` | `bulk_upsert()` | Bulk upsert rows | Pydantic `ClassificationBulkImport` |
| POST | `/api/classification/import-csv` | `import_csv()` | Upload CSV file | `UploadFile` (no content validation) |
| POST | `/api/classification/import-file` | `import_from_path()` | **Read arbitrary server file** | `path: str` — **only `os.path.isfile()` check** |
| DELETE | `/api/classification` | `clear_all()` | **Truncate entire table** | N/A |

---

## Taxonomy Router (`/api/taxonomy`) — `v2/routers/taxonomy.py`

| Method | Path | Handler | Purpose | Input Validation |
|--------|------|---------|---------|------------------|
| GET | `/api/taxonomy` | `list_rows()` | List all taxonomy entries | N/A |
| GET | `/api/taxonomy/lookup` | `taxonomy_lookup()` | Lookup map (bucket_key -> info) | N/A |
| POST | `/api/taxonomy/bulk` | `bulk_upsert()` | Bulk upsert | Pydantic `TaxonomyBulkImport` |
| POST | `/api/taxonomy/import-csv` | `import_csv()` | Upload CSV | `UploadFile` |
| DELETE | `/api/taxonomy` | `clear_all()` | **Truncate entire table** | N/A |

---

## Validation Router (`/api/validation`) — `v2/routers/validation.py`

| Method | Path | Handler | Purpose | Input Validation |
|--------|------|---------|---------|------------------|
| GET | `/api/validation` | `list_rows()` | List validation rows | `limit/offset` (no upper bound) |
| GET | `/api/validation/enriched` | `list_enriched()` | All enriched rows (**no pagination**) | N/A |
| GET | `/api/validation/count` | `row_count()` | Row count | N/A |
| POST | `/api/validation/bulk` | `bulk_insert()` | Bulk insert | Pydantic `RawRowImport` |
| POST | `/api/validation/import-csv` | `import_csv()` | Upload CSV | `UploadFile` |
| DELETE | `/api/validation` | `clear_all()` | **Truncate entire table** | N/A |

---

## Property Profile Router (`/api/prop-profile`) — `v2/routers/prop_profile.py`

| Method | Path | Handler | Purpose | Input Validation |
|--------|------|---------|---------|------------------|
| GET | `/api/prop-profile` | `list_rows()` | List rows | `limit/offset` (no upper bound) |
| GET | `/api/prop-profile/count` | `row_count()` | Row count | N/A |
| POST | `/api/prop-profile/bulk` | `bulk_insert()` | Bulk insert | Pydantic `RawRowImport` |
| POST | `/api/prop-profile/import-csv` | `import_csv()` | Upload CSV | `UploadFile` |
| DELETE | `/api/prop-profile` | `clear_all()` | **Truncate entire table** | N/A |

---

## Product Catalog Router (`/api/prop-catalog`) — `v2/routers/prop_catalog.py`

| Method | Path | Handler | Purpose | Input Validation |
|--------|------|---------|---------|------------------|
| GET | `/api/prop-catalog/code-map` | `get_code_map()` | Case-to-property map | N/A |
| GET | `/api/prop-catalog/unique-codes` | `get_unique_codes()` | Distinct property codes | N/A |
| POST | `/api/prop-catalog/code-map/bulk` | `bulk_upsert_code_map()` | Bulk upsert code map | Pydantic `PropCodeBulkImport` |
| POST | `/api/prop-catalog/code-map/import-csv` | `import_code_map_csv()` | Upload CSV | `UploadFile` |
| DELETE | `/api/prop-catalog/code-map` | `clear_code_map()` | **Truncate code map** | N/A |
| GET | `/api/prop-catalog` | `list_catalog()` | List all properties | N/A |
| GET | `/api/prop-catalog/{marsha_code}` | `get_property()` | Get one property | Path param (no validation) |
| POST | `/api/prop-catalog/bulk` | `bulk_upsert_catalog()` | Bulk upsert catalog | Pydantic `PropCatalogBulkImport` |
| POST | `/api/prop-catalog/import-csv` | `import_catalog_csv()` | Upload CSV | `UploadFile` |
| DELETE | `/api/prop-catalog` | `clear_catalog()` | **Truncate catalog** | N/A |

---

## MARSHA Mapping Router (`/api/marsha-mapping`) — `v2/routers/marsha_mapping.py`

| Method | Path | Handler | Purpose | Input Validation |
|--------|------|---------|---------|------------------|
| GET | `/api/marsha-mapping` | `get_mapping()` | Get all mappings | N/A |
| POST | `/api/marsha-mapping/bulk` | `bulk_upsert()` | Bulk upsert | Pydantic `MarshaMappingBulkImport` |
| POST | `/api/marsha-mapping/import-csv` | `import_csv()` | Upload CSV | `UploadFile` |
| DELETE | `/api/marsha-mapping` | `clear_all()` | **Truncate table** | N/A |

---

## Workbench Router (`/api/workbench`) — `v2/routers/workbench.py`

| Method | Path | Handler | Purpose | Input Validation |
|--------|------|---------|---------|------------------|
| GET | `/api/workbench/assessments` | `list_assessments()` | List filtered assessments | `limit/offset` (no max), optional `property/intent/route` |
| GET | `/api/workbench/assessments/count` | `assessment_count()` | Count | N/A |
| POST | `/api/workbench/assessments` | `create_assessment()` | Create one | Pydantic `WorkbenchAssessmentCreate` |
| POST | `/api/workbench/assessments/bulk` | `bulk_create()` | Bulk create | Pydantic `WorkbenchBulkImport` |
| PUT | `/api/workbench/assessments/{id}` | `update_assessment()` | Update one | Pydantic `WorkbenchAssessmentUpdate` |
| DELETE | `/api/workbench/assessments/{id}` | `delete_assessment()` | Delete one | Path param |
| DELETE | `/api/workbench/assessments` | `clear_all()` | **Truncate table** | N/A |
| GET | `/api/workbench/assessments/export` | `export_all()` | Export all (**no pagination**) | N/A |

---

## Conversations Router (`/api/conversations`) — `v2/routers/conversations.py`

| Method | Path | Handler | Purpose | Input Validation |
|--------|------|---------|---------|------------------|
| GET | `/api/conversations` | `list_conversations()` | List conversations (paginated, filterable) | `limit: int (1-200, default 50)`, `offset: int (ge=0)`, optional `case_id/property_code/intent` |
| POST | `/api/conversations` | `create_conversation()` | Create new conversation | Pydantic `ConversationCreate` |
| GET | `/api/conversations/{conv_id}` | `get_conversation()` | Get conversation with all messages | Path param |
| PUT | `/api/conversations/{conv_id}` | `update_conversation()` | Update conversation metadata | Pydantic `ConversationUpdate` |
| DELETE | `/api/conversations/{conv_id}` | `delete_conversation()` | Delete conversation (cascades messages) | Path param |
| POST | `/api/conversations/{conv_id}/messages` | `add_message()` | Add message to conversation | Pydantic `MessageCreate` |
| PATCH | `/api/conversations/messages/{msg_id}/feedback` | `update_message_feedback()` | Update message feedback | `dict` (JSONB) |
| DELETE | `/api/conversations` | `clear_conversations()` | **Delete all conversations** | N/A |

---

## Eval Test Cases Router (`/api/eval/testcases`) — `v2/routers/eval_testcases.py`

| Method | Path | Handler | Purpose | Input Validation |
|--------|------|---------|---------|------------------|
| GET | `/api/eval/testcases` | `list_test_cases()` | List all test cases | N/A |
| POST | `/api/eval/testcases` | `create_test_case()` | Create one | Pydantic `EvalTestCaseCreate` |
| POST | `/api/eval/testcases/bulk` | `bulk_create()` | Bulk create | Pydantic `EvalTestCaseBulkImport` |
| GET | `/api/eval/testcases/{tc_id}` | `get_test_case()` | Get one | Path param |
| PUT | `/api/eval/testcases/{tc_id}` | `update_test_case()` | Update one | Pydantic `EvalTestCaseUpdate` |
| DELETE | `/api/eval/testcases/{tc_id}` | `delete_test_case()` | Delete one | Path param |

---

## Eval Runs Router (`/api/eval`) — `v2/routers/eval_runs.py`

| Method | Path | Handler | Purpose | Input Validation |
|--------|------|---------|---------|------------------|
| GET | `/api/eval/runs` | `list_runs()` | List all runs | N/A |
| POST | `/api/eval/runs` | `create_run()` | Create run | Pydantic `EvalRunCreate` |
| GET | `/api/eval/runs/{run_id}` | `get_run()` | Get run with results | Path param |
| PUT | `/api/eval/runs/{run_id}` | `update_run()` | Update run | Pydantic `EvalRunUpdate` |
| DELETE | `/api/eval/runs/{run_id}` | `delete_run()` | Delete run (cascades) | Path param |
| POST | `/api/eval/runs/{run_id}/results` | `add_result()` | Add single result | Pydantic `EvalResultCreate` |
| POST | `/api/eval/runs/{run_id}/results/bulk` | `bulk_add_results()` | Bulk add results | Pydantic `EvalResultBulkImport` |
| POST | `/api/eval/compare` | `compare_runs()` | Compare two runs | Query: `baseline_run_id`, `comparison_run_id` |

---

## Settings Router (`/api/settings`) — `v2/routers/settings.py`

| Method | Path | Handler | Purpose | Input Validation | Notes |
|--------|------|---------|---------|------------------|-------|
| GET | `/api/settings` | `list_settings()` | List all settings | N/A | |
| GET | `/api/settings/{key}` | `get_setting()` | Get one setting | Path param | **SHADOWS routes below** |
| PUT | `/api/settings/{key}` | `set_setting()` | Set a setting | Pydantic `SettingValue` | |
| DELETE | `/api/settings/{key}` | `delete_setting()` | Delete setting | Path param | |
| GET | `/api/settings/routing-rules` | `get_routing_rules()` | Get routing rules | N/A | **UNREACHABLE (shadowed)** |
| PUT | `/api/settings/routing-rules` | `set_routing_rules()` | Set routing rules | Pydantic `RoutingRuleBulk` | |
| GET | `/api/settings/aggregations` | `get_aggregations()` | Get aggregations | N/A | **UNREACHABLE (shadowed)** |
| PUT | `/api/settings/aggregations` | `set_aggregations()` | Set aggregations | Pydantic `SettingValue` | |

---

## Feedback Router (`/api/feedback`) — `v2/routers/feedback.py`

| Method | Path | Handler | Purpose | Input Validation |
|--------|------|---------|---------|------------------|
| GET | `/api/feedback/taxonomy` | `get_taxonomy_feedback()` | Get all taxonomy feedback | N/A |
| PUT | `/api/feedback/taxonomy/{bucket_key}` | `set_taxonomy_feedback()` | Set feedback | **Bare `dict` (no model)** |
| DELETE | `/api/feedback/taxonomy/{bucket_key}` | `delete_taxonomy_feedback()` | Delete feedback | Path param |
| GET | `/api/feedback/messages` | `get_message_feedback()` | Get all message feedback | N/A |
| PUT | `/api/feedback/messages/{message_key}` | `set_message_feedback()` | Set feedback | **Bare `dict` (no model)** |
| DELETE | `/api/feedback/messages/{message_key}` | `delete_message_feedback()` | Delete feedback | Path param |

---

## CSV Import Router (`/api/import`) — `v2/routers/csv_import.py`

| Method | Path | Handler | Purpose | Input Validation |
|--------|------|---------|---------|------------------|
| POST | `/api/import/csv` | `import_csv()` | Dispatch CSV import by type | `type` validated against allowlist |

---

## Migration Router (`/api/migrate`) — `v2/routers/migrate.py`

| Method | Path | Handler | Purpose | Input Validation |
|--------|------|---------|---------|------------------|
| POST | `/api/migrate/from-indexeddb` | `migrate_from_indexeddb()` | Full data migration from v1 | Pydantic `MigrationPayload` |
| GET | `/api/migrate/status` | `migration_status()` | Check migration status | N/A |

---

## Aggregations Router (`/api/aggregations`) — `v2/routers/aggregations.py`

| Method | Path | Handler | Purpose | Input Validation |
|--------|------|---------|---------|------------------|
| GET | `/api/aggregations` | `get_aggregations()` | Get cached aggregations | N/A |
| POST | `/api/aggregations/compute` | `compute_and_store()` | Recompute all aggregations (expensive) | N/A |

---

## LLM Proxy Router (`/api/llm`) — `v2/routers/llm_proxy.py`

All LLM traffic is proxied through these endpoints. API keys stay server-side.

| Method | Path | Handler | Purpose | Input Validation |
|--------|------|---------|---------|------------------|
| GET | `/api/llm/config` | `get_config()` | Read LLM config (endpoints, masked key) | N/A |
| PUT | `/api/llm/config` | `update_config()` | Update LLM endpoints/API key (stored in settings table) | `LLMConfigUpdate` Pydantic model |
| GET | `/api/llm/models` | `list_models()` | List available models from upstream | `backend` query param |
| POST | `/api/llm/chat` | `chat_stream()` | Streaming chat completion proxy | `ChatRequest` Pydantic model |
| POST | `/api/llm/chat/sync` | `chat_sync()` | Non-streaming chat completion proxy | `ChatRequest` Pydantic model |

Config priority: DB settings (`llm_config` key) → environment variables → defaults.

---

## Summary Statistics

- **Total endpoints:** ~75
- **Authenticated endpoints:** 0
- **Endpoints with Pydantic validation:** ~28
- **Endpoints with bare dict body:** 2 (feedback)
- **Destructive DELETE (truncate) endpoints:** 9
- **Endpoints with no pagination:** 3 (enriched, export_all, list_enriched)
- **Shadowed/unreachable endpoints:** 2 (settings router bug)
