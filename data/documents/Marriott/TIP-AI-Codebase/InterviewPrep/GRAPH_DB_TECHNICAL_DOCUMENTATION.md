# Graph Database (Neo4j) - Technical Documentation

**Project:** emergingtech-tipai-orchestrator
**Technology:** Neo4j 5.21 Community Edition + APOC Plugin
**Query Language:** Cypher
**Python Driver:** `neo4j>=5.20.0,<6`

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Graph Schema](#graph-schema)
3. [Data Ingestion Pipeline](#data-ingestion-pipeline)
4. [Query Layer and Tool API](#query-layer-and-tool-api)
5. [Orchestrator Integration](#orchestrator-integration)
6. [Intent Graph (DAG) - Separate Concept](#intent-graph-dag)
7. [Infrastructure and Configuration](#infrastructure-and-configuration)
8. [File Reference Map](#file-reference-map)
9. [Interview Q&A](#interview-qa)

---

## 1. Architecture Overview

The project uses **two distinct graph concepts**:

| Concept | Technology | Purpose |
|---|---|---|
| **Neo4j Knowledge Graph (KG)** | Neo4j 5.21, Cypher | Stores hotel properties, recreation activities, and credit cards as a property graph. Queried by LLM tools at runtime. |
| **Intent Graph (DAG)** | In-memory Python dataclass | A directed acyclic graph of decomposed user intents. Built per-request by the LLM, validated with Tarjan's SCC algorithm, executed by the orchestrator's `NodeScheduler`. Not stored in any database. |

### End-to-End Data Flow

```
JSON files (12 hotels)
    |
    v
graph/compile_graph.py (GraphLoader)
    |  MERGE nodes, MERGE edges
    v
Neo4j 5.21 (bolt://neo4j:7687)
    ^
    |  Cypher queries via neo4j Python driver
    |
app/tools/graph_tools.py (8 kg_* tool functions)
    ^
    |  graph_tool_handler() dispatch
    |
app/tools/__init__.py (get_handler routes "kg*" prefix)
    ^
    |  ToolDefinition schemas in tool_registry.py
    |
LLM Tool Planner (agent_toolPlanner activity)
    ^
    |
User query via orchestrator workflow
```

### Docker Dependency Chain

```
neo4j (starts, healthcheck passes)
  -> graph-loader (loads data via compile_graph.py, exits)
    -> worker (starts, connects to Neo4j for runtime queries)
```

---

## 2. Graph Schema

Defined declaratively in `graph/config/nodes_and_edges.yaml`.

### Node Types (3)

| Neo4j Label | Key Property | Source JSON Path | Properties |
|---|---|---|---|
| `Property` | `_id` | `propertyInformation` | `propertyDisplayName`, `_id`, `propertyId`, `ContextID`, `propertyCode`, `city`, `maxMeetingSpace`, `meetingRoomCount`, `amenities`, `hoursOfOperation`, `address`, `phoneNumbers` |
| `CreditCard` | `code` | `creditCards` | `code`, `description` |
| `RecreationType` | `type` | `recreationActivities` | `type` |

### Edge Types (2)

| Relationship | From | To | Edge Properties |
|---|---|---|---|
| `HasCreditCard` | `Property` | `CreditCard` | `externalRecordID`, `status` |
| `HasRecreation` | `Property` | `RecreationType` | `name`, `locationType`, `distance` |

### Visual Schema

```
(Property) --[HasCreditCard {externalRecordID, status}]--> (CreditCard)
(Property) --[HasRecreation {name, locationType, distance}]--> (RecreationType)
```

### Key Design Decision

Activity-specific details (`name`, `locationType`, `distance`) are stored **on the `HasRecreation` edge**, not on the `RecreationType` node. This allows a single `RecreationType` node (e.g., `water_recreation_activities`) to be shared across many properties, with each edge carrying the specific activity details. This is a textbook property-graph modeling pattern that avoids node explosion.

### Sample Data Shape (hotel1_en_us.json)

```json
{
  "propertyInformation": {
    "propertyDisplayName": "Marriott Austin Downtown",
    "_id": "PropertyCache.hotel1_en_US",
    "propertyCode": "hotel1",
    "city": "Austin"
  },
  "recreationActivities": [
    {
      "type": "water_recreation_activities",
      "name": "Jet Ski",
      "locationType": "Nearby",
      "distance": "8.4 miles"
    }
  ],
  "creditCards": [
    { "code": "VI", "description": "Visa" }
  ]
}
```

---

## 3. Data Ingestion Pipeline

**File:** `graph/compile_graph.py`
**Entry point:** `python graph/compile_graph.py` (run by Docker `graph-loader` service)

### GraphLoader Class

```python
class GraphLoader:
    def __init__(uri, user, password, db)  # Initializes Neo4j driver
    def clear_graph()                       # MATCH (n) DETACH DELETE n
    def upsert_node(label, key_prop, item, prop_list)  # MERGE + SET
    def upsert_edge(from_label, ..., rel_type, rel_props)  # MERGE + SET
```

### Ingestion Flow

1. **Load config**: Reads `graph/config/nodes_and_edges.yaml`, validates all node/edge definitions have required fields (`LABEL`, `KEY`, `SOURCE`, `PROPERTIES_LIST` for nodes; `TYPE`, `FROM`, `TO`, `SOURCE`, `REL_PROPERTIES_LIST` for edges).

2. **Optional reset**: If `RESET_KG=true` (env var), clears the entire graph with `MATCH (n) DETACH DELETE n`.

3. **Iterate JSON files**: Processes all 12 `graph/data/hotel*_en_us.json` files in sorted order.

4. **Upsert nodes**: For each node config, extracts source data from JSON, calls `upsert_node()` which generates:
   ```cypher
   MERGE (n:Property { _id: $key })
   SET n += $props
   ```

5. **Upsert edges**: For each edge config, iterates source items and calls `upsert_edge()`:
   ```cypher
   MERGE (a:Property { _id: $fromKey })
   MERGE (b:RecreationType { type: $toKey })
   MERGE (a)-[r:HasRecreation]->(b)
   SET r += $relProps
   ```

6. **Verify**: Runs `verify_counts()` to log final node/relationship counts.

### Helper Functions

| Function | Purpose |
|---|---|
| `_is_neo4j_primitive()` | Checks if value is a Neo4j-compatible primitive |
| `_coerce_neo4j_value()` | Converts lists/dicts to JSON strings for Neo4j storage |
| `_quote_ident()` | Prevents Cypher injection by validating/quoting identifiers |
| `_as_list()` | Normalizes dict or list source data to a list |
| `_load_config()` | Loads and validates YAML config |

---

## 4. Query Layer and Tool API

**File:** `app/tools/graph_tools.py`

### Connection Management

```python
NEO4J_URI      = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER     = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_DB       = os.getenv("NEO4J_DB", "neo4j")

_DRIVER = None  # Lazy singleton, reused across requests
```

- `_get_driver()` - Lazy-initializes a singleton Neo4j driver
- `_run(query, params)` - Core Cypher executor, returns `list[dict]`
- `_safe_run(query, params)` - Wraps `_run()` with error context for debugging

### The 8 KG Tools

#### 1. `kg_schema_catalog` - Full Schema Introspection

Returns labels, properties, relationship types, value hints, indexes, constraints. Uses a **TTL-based cache** (default 5 minutes) to avoid repeated schema queries.

```cypher
CALL db.schema.nodeTypeProperties() ...
CALL db.schema.relTypeProperties() ...
MATCH (n) UNWIND labels(n) AS l RETURN l AS label, count(*) AS cnt
MATCH ()-[r]->() RETURN type(r) AS rel, count(*) AS cnt
SHOW INDEXES / SHOW CONSTRAINTS
```

Also collects **value hints** (distinct values for RecreationType.type and CreditCard.code) used for fuzzy matching.

#### 2. `kg_schema_summary` - Lightweight Schema

```cypher
CALL db.labels()
CALL db.relationshipTypes()
```

Returns just label names and relationship type names.

#### 3. `kg_resolve_property` - Property Lookup

Multi-predicate search across `_id`, `propertyCode`, `propertyId`, name (CONTAINS), and city:

```cypher
MATCH (p:Property)
WHERE ($id IS NOT NULL AND p._id = $id)
   OR ($propertyCode IS NOT NULL AND p.propertyCode = $propertyCode)
   OR ($name IS NOT NULL AND toLower(p.propertyDisplayName) CONTAINS toLower($name))
   OR ($city IS NOT NULL AND toLower(p.city) = toLower($city))
RETURN p._id AS id, p.propertyDisplayName AS name, p.city AS city ...
LIMIT coalesce($limit, 25)
```

#### 4. `kg_get_property_overview` - Single Property Deep-Dive

Multi-hop pattern matching with OPTIONAL MATCH for recreation and credit cards:

```cypher
MATCH (p:Property)
WHERE p._id = $id OR p.propertyCode = $propertyCode OR p.propertyDisplayName = $name
OPTIONAL MATCH (p)-[:HasRecreation]->(rt:RecreationType)
OPTIONAL MATCH (p)-[rel:HasRecreation]->(:RecreationType)
OPTIONAL MATCH (p)-[:HasCreditCard]->(cc:CreditCard)
RETURN ... recreationTypes, cardCodes, sampleActivities
```

Returns property details plus all connected recreation types, credit cards, and activity samples. JSON-encoded fields (`amenities`, `hoursOfOperation`, `address`, `phoneNumbers`) are parsed back with `_parse_json_if_string()`.

#### 5. `kg_search_properties` - Faceted Search (Most Complex)

Multi-filter search with city, recreation types, card codes, meeting space, and distance:

```cypher
MATCH (p:Property)
OPTIONAL MATCH (p)-[:HasRecreation]->(rt:RecreationType)
WITH p, collect(DISTINCT rt.type) AS rtypes
OPTIONAL MATCH (p)-[:HasCreditCard]->(cc:CreditCard)
WITH p, rtypes, collect(DISTINCT cc.code) AS cards
WHERE ($city IS NULL OR toLower(p.city) = toLower($city))
  AND ($recreationTypes IS NULL OR any(t IN $recreationTypes WHERE t IN rtypes))
  AND ($cardCodes IS NULL OR any(c IN $cardCodes WHERE c IN cards))
  AND ($minMeetingSpace IS NULL OR p.maxMeetingSpace >= $minMeetingSpace)
```

Includes Cypher-level distance parsing from edge properties and a **Python-side safety net** that re-filters results for distance constraints.

#### 6. `kg_find_similar_properties` - Similarity via Shared Recreation

Multi-hop traversal to find properties sharing recreation types:

```cypher
MATCH (seed:Property)-[:HasRecreation]->(rt:RecreationType)
MATCH (p:Property)-[:HasRecreation]->(rt)
WHERE p <> seed
WITH p, collect(DISTINCT rt.type) AS sharedTypes, size(sharedTypes) AS score
ORDER BY score DESC
```

Scores by count of shared recreation types.

#### 7. `kg_recreation_within_distance` - Distance-Filtered Activities

Returns (property, activity) pairs within a max distance:

```cypher
MATCH (p:Property)-[rel:HasRecreation]->(rt:RecreationType)
-- distance parsing from edge properties
WITH p, rt, rel,
  CASE
    WHEN d =~ '^\s*[0-9]*\.?[0-9]+\s*(miles?|mi)?\s*$'
      THEN toFloat(split(d, ' ')[0])
    WHEN lt IN ['onsite','on-site','on site'] THEN 0.0
    WHEN lt = 'nearby' THEN 1.0
    ELSE NULL
  END AS miles
WHERE $maxMiles IS NULL OR (miles IS NOT NULL AND miles <= $maxMiles)
```

#### 8. `kg_explain_paths` - Path Explanation Between Two Properties

```cypher
MATCH path = (p1)-[:HasRecreation]->(rt:RecreationType)<-[:HasRecreation]-(p2)
RETURN DISTINCT
  [n IN nodes(path) | coalesce(n.propertyDisplayName, n.type, n.code)] AS nodes,
  [r IN relationships(path) | type(r)] AS rels
```

Produces human-readable path explanations like:
`Marriott Austin -> [HasRecreation] -> water_recreation_activities -> [HasRecreation] -> Ritz Carlton`

### Query Helper Functions

| Function | Purpose |
|---|---|
| `_jsonify()` | Converts Neo4j types (Date, Time, Duration, bytes) to JSON-safe |
| `_parse_json_if_string()` | Parses JSON-encoded string properties back to objects |
| `_none_if_blank()` | Normalizes "any", "all", "*", empty strings to None |
| `_normalize_filters()` | Applies blank-normalization to all filter args |
| `_parse_distance_miles()` | Parses "8.4 miles", "nearby", "onsite" to float |
| `_canonicalize_values()` | Fuzzy-matches user input to known enum values using `difflib.get_close_matches` |
| `_map_search_parameters()` | Maps "American Express" -> "AM", "Water activities" -> "water_recreation_activities" |
| `_get_schema_catalog_cached()` | Schema catalog with configurable TTL cache |

---

## 5. Orchestrator Integration

### Tool Registration

**File:** `app/tools/tool_registry.py`

All 7 KG tools (excluding `kg_schema_summary`) are registered as `ToolDefinition` objects with typed `ToolArgument` schemas. These definitions are presented to the LLM during tool planning so it knows what tools are available and their parameter types.

```python
kg_search_properties_tool = ToolDefinition(
    name="KgSearchProperties",
    description="Perform a faceted search over properties with optional filters.",
    arguments=[
        ToolArgument(name="city", type="string", ...),
        ToolArgument(name="recreationTypes", type="array", ...),
        ToolArgument(name="cardCodes", type="array", ...),
        ToolArgument(name="minMeetingSpace", type="number", ...),
        ToolArgument(name="maxDistanceMiles", type="number", ...),
        ToolArgument(name="limit", type="integer", ...),
    ],
    requires_confirmation=False,
)
```

### Tool Dispatch Flow

**File:** `app/tools/__init__.py`

```
User Query
  -> LLM Tool Planner (agent_toolPlanner activity)
    -> Selects kg_* tools based on ToolDefinition schemas
      -> get_handler(tool_name) checks if name starts with "kg"
        -> Wraps graph_tool_handler(tool_name, args)
          -> Normalizes tool name to alphanumeric lowercase
            -> Routes to specific kg_* function
              -> Cypher query against Neo4j
                -> JSON result returned to LLM
```

### Intent Registration for Graph Search

**File:** `scripts/create_graph_intent.py`

A `graph_search` intent is registered in the intent registry so the orchestrator's intent mapping can route hotel/property search queries to KG tools:

```python
payload = {
    "name": "graph_search",
    "title": "Graph Search",
    "description": "Search for hotels and activities using the Knowledge Graph.",
    "domain": "search",
    "semantics": {
        "examples": {
            "positive": ["find hotels in New York", "show me hotels with a pool", ...],
            "negative": ["what is the cancellation policy?", ...]
        }
    }
}
```

---

## 6. Intent Graph (DAG)

This is a **separate concept** from the Neo4j Knowledge Graph. The Intent Graph is an in-memory DAG representing the execution plan for a user's multi-part request.

### Data Models

**File:** `app/models/intent_graph.py`

```python
@dataclass
class IntentNode:
    id: str
    intent_id: str
    params: Dict[str, Any]
    dependencies: List[str]
    parallel: bool = False
    confidence: Optional[float] = None
    intent_name: Optional[str] = None

@dataclass
class UnknownIntentNode:
    id: str
    unknown_intent_ref: str
    original_query: Optional[str] = None
    error_message: str = ""
    dependencies: List[str] = field(default_factory=list)

@dataclass
class IntentGraph:
    nodes: List[Union[IntentNode, UnknownIntentNode]]
    unmatched_metadata: Optional[UnmatchedQueryMetadata] = None
```

### Graph Processing Pipeline

**File:** `app/intent_mapping/graph_processor.py`

The `GraphProcessor` class handles the full pipeline:

1. **validate_graph_structure()** - Validates nodes have IDs, dependencies reference valid nodes, params contain `sub_query`
2. **_detect_cycles()** - DFS-based cycle detection
3. **collapse_cycles()** - Tarjan's SCC algorithm merges cyclic nodes into single nodes
4. **merge_nodes_by_intent()** - Deduplicates nodes referencing the same intent
5. **build_intent_graph()** - Full pipeline: validate -> collapse cycles -> build nodes -> deduplicate

### Node Scheduling

**File:** `app/workflows/orchestrator_components/node_scheduler.py`

The `NodeScheduler` resolves dependencies and executes nodes:

```python
class NodeScheduler:
    def get_ready_nodes(nodes_by_id)  # Returns nodes with all deps met
    def mark_started(node_id)
    def mark_completed(node_id)
    def is_all_complete(total_nodes)
    def cancel_all_in_flight()        # For user interruption
```

Parallel nodes execute concurrently; sequential nodes wait for dependencies.

---

## 7. Infrastructure and Configuration

### Neo4j Docker Service

```yaml
neo4j:
  image: neo4j:5.21-community
  environment:
    NEO4J_AUTH: neo4j/password
    NEO4J_PLUGINS: '["apoc"]'
    NEO4J_server_memory_heap_initial__size: 768m
    NEO4J_server_memory_heap_max__size: 768m
  ports:
    - "7474:7474"   # Browser UI
    - "7687:7687"   # Bolt protocol
  healthcheck:
    test: ["CMD-SHELL", "cypher-shell -u neo4j -p password 'RETURN 1' || exit 1"]
```

### Graph Loader Service

```yaml
graph-loader:
  depends_on:
    neo4j:
      condition: service_healthy
  environment:
    NEO4J_URI: bolt://neo4j:7687
    RESET_KG: "true"
  command: python graph/compile_graph.py
  restart: "no"  # One-shot: runs, loads data, exits
```

### Worker Service (Neo4j Consumer)

```yaml
worker:
  depends_on:
    neo4j:
      condition: service_healthy
    graph-loader:
      condition: service_completed_successfully  # Waits for load to finish
```

### Application Configuration

| Setting | Env Var | Default | Purpose |
|---|---|---|---|
| `schema_cache_ttl_seconds` | `SCHEMA_CACHE_TTL_SECONDS` | 300 (5 min) | TTL for cached schema catalog |
| `fuzzy_match_cutoff` | `FUZZY_MATCH_CUTOFF` | 0.6 | Cutoff for fuzzy enum matching |
| `NEO4J_URI` | `NEO4J_URI` | `bolt://neo4j:7687` | Neo4j Bolt endpoint |
| `NEO4J_USER` | `NEO4J_USER` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | `NEO4J_PASSWORD` | `password` | Neo4j password |
| `NEO4J_DB` | `NEO4J_DB` | `neo4j` | Database name |

---

## 8. File Reference Map

### Core Graph Files

| File | Purpose |
|---|---|
| `graph/config/nodes_and_edges.yaml` | Declarative schema: node labels, edge types, property mappings |
| `graph/compile_graph.py` | `GraphLoader` class: reads JSON, upserts nodes/edges into Neo4j |
| `graph/data/hotel{1-12}_en_us.json` | 12 source JSON data files (hotel property data) |
| `graph/graph_questions.md` | Example use-case queries demonstrating KG tool usage |

### Application Layer

| File | Purpose |
|---|---|
| `app/tools/graph_tools.py` | All 8 `kg_*` tool functions, Neo4j connection, Cypher queries |
| `app/tools/tool_registry.py` | Registers KG tools as `ToolDefinition` objects for LLM tool-calling |
| `app/tools/__init__.py` | Routes `kg*` tool names to `graph_tool_handler` |

### Intent Graph (DAG)

| File | Purpose |
|---|---|
| `app/models/intent_graph.py` | `IntentNode`, `UnknownIntentNode`, `IntentGraph` dataclasses |
| `app/intent_mapping/graph_processor.py` | Validation, cycle detection (Tarjan's), SCC merging, deduplication |
| `app/workflows/orchestrator_components/node_scheduler.py` | Dependency-based execution scheduling |

### Configuration

| File | Purpose |
|---|---|
| `app/infrastructure/config/models.py` | `SearchConfig` with `schema_cache_ttl_seconds`, `fuzzy_match_cutoff` |
| `docker/docker-compose.yml` | Neo4j service, graph-loader, worker dependency chain |

### Scripts and Tests

| File | Purpose |
|---|---|
| `scripts/create_graph_intent.py` | Creates `graph_search` intent in the registry |
| `scripts/verify_graph_api.py` | E2E test: sends hotel search queries, verifies KG tools fire |
| `scripts/run_property_graph_eval.py` | Evaluation harness: runs prompts against all 12 properties |
| `docs/PROPERTY_DATA_INVENTORY.md` | Documents what data is/isn't available in the graph |

---

## 9. Interview Q&A

### Q: Why Neo4j over a relational database for this use case?

**A:** Three reasons:
1. **Multi-hop traversal** is native. Finding "hotels similar to X based on shared recreation types" is a 2-hop path (Property -> RecreationType -> Property) that's a single MATCH pattern in Cypher but requires multiple JOINs in SQL.
2. **Edge properties** store activity-specific details (distance, location type) naturally on relationships, avoiding junction-table complexity.
3. **Schema flexibility** - the YAML config drives ingestion, so adding new node/edge types doesn't require DDL migrations.

### Q: How does the schema catalog caching work?

**A:** `_get_schema_catalog_cached()` uses a global dict with a timestamp. If the cache is younger than `schema_cache_ttl_seconds` (default 300s), it returns cached data. Otherwise it runs 6+ Cypher queries (node properties, rel properties, label counts, rel counts, indexes, constraints, value hints) and refreshes the cache. The value hints (distinct RecreationType.type and CreditCard.code values) are crucial for fuzzy matching.

### Q: How does fuzzy matching work for user input?

**A:** The `_canonicalize_values()` function takes user-provided values (e.g., "tour") and matches them against known enum values from the schema catalog using `difflib.get_close_matches` with a configurable cutoff (default 0.6). Additionally, `_map_search_parameters()` handles explicit mappings like "American Express" -> "AM" and "Water activities" -> "water_recreation_activities".

### Q: What is the difference between the Neo4j KG and the Intent Graph?

**A:** They are completely separate:
- **Neo4j KG**: A persistent property graph database storing hotel data. Queried via Cypher at runtime.
- **Intent Graph**: An in-memory Python DAG built per-request by the LLM. Represents the execution plan for a user's compound query (e.g., "find hotels near water activities AND check if they accept Visa"). Validated with Tarjan's SCC algorithm for cycle detection, then executed by `NodeScheduler`.

### Q: How does the graph-loader Docker service work?

**A:** It's a **one-shot container**: depends on Neo4j being healthy, runs `python graph/compile_graph.py` to load all 12 JSON files, then exits. The worker service has `condition: service_completed_successfully` on the graph-loader, ensuring it only starts after data is fully loaded.

### Q: How does distance filtering work in kg_search_properties?

**A:** Two-layer approach:
1. **Cypher-level**: Parses distance strings (e.g., "8.4 miles") using regex, handles "onsite" (0.0 mi) and "nearby" (1.0 mi) as special cases, computes `min(miles)` per property.
2. **Python safety net**: Re-filters results in Python using `_parse_distance_miles()` to catch any edge cases the Cypher regex missed.

### Q: How does the MERGE strategy prevent duplicates?

**A:** Neo4j `MERGE` is an atomic "find or create" operation. Nodes are merged on their key property (`_id` for Property, `code` for CreditCard, `type` for RecreationType). Edges are merged on the combination of from-node, to-node, and relationship type. The `SET n += $props` updates properties on existing nodes/edges without creating duplicates.

### Q: Walk through a user query like "Find hotels in Austin with water activities within 2 miles that accept Visa."

**A:**
1. Intent mapping routes to `graph_search` intent
2. LLM tool planner selects `KgSearchProperties`
3. `_map_search_parameters()` maps "Visa" -> "VI"
4. `_canonicalize_values()` fuzzy-matches "water activities" -> "water_recreation_activities"
5. Cypher query filters Property nodes by city="Austin", traverses HasRecreation edges to RecreationType where type matches, checks HasCreditCard edges for "VI", and parses distance from HasRecreation edge properties
6. Results returned as JSON with property details, matched recreation types, card codes, and minimum distance
