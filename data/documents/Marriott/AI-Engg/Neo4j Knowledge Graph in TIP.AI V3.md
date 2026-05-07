

## Neo4j Knowledge Graph in TIP.AI V3

### 1. What is Neo4j Knowledge Graph?

Neo4j is a graph database that stores data as nodes and relationships. In this project, it models:
- Hotels/Properties (nodes)
- Recreation types (nodes)
- Credit cards (nodes)
- Relationships like `HasRecreation`, `AcceptsCard`, `LocatedIn`

Why use a graph here:
- Multi-hop queries (e.g., hotels near recreation types)
- Relationship traversal (e.g., similar hotels via shared recreation types)
- Schema discovery (canonicalize user terms like "tour" → `tour_recreation_activities`)

### 2. Location in Workspace

Neo4j is set up in multiple places:

#### A. Docker Container
```yaml
# docker/docker-compose.yml (lines 53-74)
neo4j:
  image: neo4j:5.21-community
  container_name: neo4j
  ports:
    - "7474:7474"  # HTTP (Browser UI)
    - "7687:7687"  # Bolt (Query protocol)
```

Access:
- Neo4j Browser: http://localhost:7474 (user: `neo4j`, password: `password`)
- Bolt connection: `bolt://neo4j:7687`

#### B. Code Implementation
```
mi-tipv3-alpha/
├── graph/                          # Knowledge graph management
│   ├── compile_graph.py           # Neo4j graph initialization
│   ├── config/
│   │   └── nodes_and_edges.yaml   # Graph schema definition
│   ├── data/                      # Hotel/property JSON data files
│   │   ├── hotel1_en_us.json
│   │   ├── hotel2_en_us.json
│   │   └── ...
│   └── graph_questions.md         # Example queries
│
└── app/tools/
    └── graph_tools.py             # Knowledge graph query tools
```

#### C. Graph Loader Container
```yaml
# docker-compose.yml
graph-loader:
  # Initializes Neo4j with hotel/property data
  # Runs compile_graph.py to load data
```

### 3. How It's Used for Responding to User Prompts

#### Step 1: Intent Identification
When a user asks: "Find me hotels within 1 mile of tour activities that accept Discover"

The orchestrator:
1. Maps the query to `intent_property_graph_qa`
2. Routes to the executor workflow

#### Step 2: Knowledge Graph Tools Execution
The `intent_property_graph_qa` intent uses tools from `graph_tools.py`:

Available tools:
1. `KgSchemaCatalog` — Discover valid values (e.g., "tour" → `tour_recreation_activities`)
2. `KgSearchProperties` — Search hotels with filters
3. `KgGetPropertyOverview` — Get details for a specific property
4. `KgFindSimilarProperties` — Find similar hotels
5. `KgRecreationWithinDistance` — Find hotels near recreation types
6. `KgExplainPaths` — Explain relationships between nodes

#### Step 3: Example Flow

```python
# User: "Find hotels within 1 mile of tour activities that accept Discover"

# 1. Schema Discovery
KgSchemaCatalog() 
# Returns: {
#   "RecreationType.type": ["tour_recreation_activities", ...],
#   "CreditCard.code": ["DI" (Discover), ...]
# }

# 2. Search Properties
KgSearchProperties({
    "recreationTypes": ["tour_recreation_activities"],
    "cardCodes": ["DI"],
    "maxDistanceMiles": 1.0
})
# Returns: List of matching hotels with distances

# 3. LLM formats response with citations
```

#### Step 4: Multi-Step Reasoning
For complex queries like "Show me hotels similar to Ritz Carlton New York":

```python
# 1. Get seed property details
KgGetPropertyOverview({"propertyName": "Ritz Carlton New York"})
# Returns: recreationTypes, location, etc.

# 2. Find similar properties
KgFindSimilarProperties({
    "seedProperty": "Ritz Carlton New York",
    "recreationTypes": [...]  # From step 1
})

# 3. Explain why they're similar
KgExplainPaths({
    "from": "Ritz Carlton New York",
    "to": "Candidate Hotel"
})
# Returns: Path explanation like:
# "Ritz Carlton → HasRecreation → RecreationType ← HasRecreation ← Candidate"
```

### 4. Connection Configuration

```python
# app/tools/graph_tools.py (lines 13-16)
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_DB = os.getenv("NEO4J_DB", "neo4j")
```

### 5. Data Structure

The graph contains:
- Nodes: `Property`, `RecreationType`, `CreditCard`, `City`
- Relationships: `HasRecreation`, `AcceptsCard`, `LocatedIn`
- Properties: Distance on edges, hotel attributes on nodes

Example query (Cypher):
```cypher
MATCH (p:Property)-[r:HasRecreation]->(rec:RecreationType)
WHERE rec.type = 'tour_recreation_activities'
  AND r.distanceMiles <= 1.0
  AND (p)-[:AcceptsCard]->(:CreditCard {code: 'DI'})
RETURN p.name, r.distanceMiles
```

### Summary

- Location: Docker container (`neo4j:5.21-community`) + code in `graph/` and `app/tools/graph_tools.py`
- Purpose: Answer complex hotel/property queries with relationships and multi-hop reasoning
- Usage: Via `intent_property_graph_qa` intent → calls graph tools → executes Cypher queries → returns results
- Access: Browser UI at http://localhost:7474, Bolt at `bolt://neo4j:7687`

The knowledge graph enables queries that would be complex in SQL, such as finding hotels near specific recreation types, discovering similar properties, and explaining relationships.