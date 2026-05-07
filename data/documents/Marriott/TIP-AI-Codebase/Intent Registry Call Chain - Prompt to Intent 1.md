# Intent Registry Call Chain - Prompt to Intent

> How the orchestrator queries the `intent_registry` database to identify which intent to call for a user prompt.
>
> - **Table:** `intents`
> - **Database:** `intent_registry`
> - **Schema:** `intent_registry_schema`

---

## The Class: `IntentRegistryClient`

The primary Python class that directly queries the `intent_registry` database (schema `intent_registry_schema`, table `intents`) is **`IntentRegistryClient`** located at:

```
emergingtech-tipai-orchestrator/app/registry/client.py
```

It connects using the `intent_registry_schema` search path:

```python
"options": "-c search_path=intent_registry_schema",
```

### Key methods that query the `intents` table

| Method | Purpose |
|--------|---------|
| `get_intent_by_id()` | Lookup a single intent by its numeric ID |
| `find_intent_by_name()` | Lookup a single intent by its `name` column |
| `get_active_intents()` | Get all intents with `status = 'active'` (optionally filtered by team) |
| `search_by_keywords()` | Search intents using TF-IDF keyword extraction against the `keywords` array column |
| `search_by_utterance_patterns()` | Regex-match the user utterance against each intent's `semantics->>'utterance_pattern'` |
| `search_by_embedding_similarity()` | Cosine similarity search using pgvector against the `embedding` column, with negative embedding filtering |

---

## Full Call Chain (Prompt to Intent)

The end-to-end flow is a **4-class chain**:

### 1. `IntentMapper` (Workflow Component)

**File:** `app/workflows/orchestrator_components/intent_mapper.py`

Temporal workflow component that initiates the mapping by calling the Temporal activity.

### 2. `agent_mapPromptToGraph` (Temporal Activity)

**File:** `app/activities/intent_mapping.py`

The Temporal activity function. It creates a `PromptMapper` with an `IntentSearchService` and delegates the work.

### 3. `PromptMapper`

**File:** `app/intent_mapping/prompt_mapper.py`

Orchestrates the mapping pipeline:
1. Decomposes the user prompt into sub-queries via LLM
2. Searches for candidate intents (via `IntentSearchService`)
3. Uses LLM to generate a DAG mapping sub-queries to intents
4. Returns a validated `IntentGraph`

### 4. `IntentSearchService`

**File:** `app/intent_mapping/intent_search_service.py`

Runs **three search methods in parallel** against the registry using `IntentRegistryClient`:
- Keyword search (`search_by_keywords`)
- Utterance pattern search (`search_by_utterance_patterns`)
- Embedding similarity search (`search_by_embedding_similarity`)

Deduplicates and filters results by similarity threshold.

### 5. `IntentRegistryClient`

**File:** `app/registry/client.py`

**This is the class that directly executes SQL against the `intent_registry` database**, querying the `intent_registry_schema.intents` table via `psycopg2`. It also uses Redis for caching.

---

## Visual Flow

```
IntentMapper (workflow component)
  └─> agent_mapPromptToGraph (Temporal activity)
        └─> PromptMapper.map_prompt_to_graph()
              ├─> LLM: decompose prompt into sub-queries
              ├─> IntentSearchService.search_per_subquery()
              │     └─> IntentRegistryClient  ← queries intent_registry DB
              │           ├─ search_by_keywords()
              │           ├─ search_by_utterance_patterns()
              │           └─ search_by_embedding_similarity()
              └─> LLM: map sub-queries to best-matching intents → IntentGraph
```

---

## Database Schema

The `intents` table is defined in `app/database/init/01-create-intent-registry-schema.sql`:

```sql
CREATE TABLE intent_registry_schema.intents (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    domain TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT '1.0.0',
    owner_team TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'preview', 'deprecated')),
    semantics JSONB,        -- Keywords, examples, patterns
    routing JSONB,          -- Execution routing (optional)
    keywords TEXT[],
    embedding VECTOR(3072), -- Positive examples embedding
    negative_embedding VECTOR(3072), -- Negative examples embedding
    example_conversation_history TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

*Source: `emergingtech-tipai-orchestrator` codebase analysis — April 2026*
