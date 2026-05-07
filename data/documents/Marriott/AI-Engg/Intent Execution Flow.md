
Here is the intent execution flow

Step 1- keyword search 
uses postgres sql 


```python
# From intent_search_service.py, line 151-210
def _search_all_methods(self, query: str) -> List[AgentIntent]:
    # All three methods run in parallel
    keyword_results = self.registry_client.search_by_keywords(query)
    pattern_results = self.registry_client.search_by_utterance_patterns(query)
    embedding_results = self.registry_client.search_by_embedding_similarity(query)
    # Results are combined and deduplicated
```


## Intent identification: hybrid approach

The system uses three methods in parallel to identify intents:

### 1. Keyword search (search_by_keywords)

- Searches the keywords array field in the database

- Uses PostgreSQL array containment (@>) for matching

- For the policy intent, keywords include: ["policy", "bonvoy", "late checkout", "refund", "rebooking", "terms", "conditions", "elite benefits"]

### 2. Pattern/regex search (search_by_utterance_patterns)

- Uses regex matching against utterance_pattern in the semantics JSONB field

- For the policy intent, pattern is: "policy|bonvoy.*rules|late.*checkout|refund.*policy|elite.*benefit|early.*check.*in"

### 3. Semantic/embedding search (search_by_embedding_similarity)

- Uses vector similarity search with pgvector

- Generates embeddings for the user query using EmbeddingService

- Compares against stored intent embeddings using cosine similarity

- Default similarity threshold: 0.3

### How it works

# From intent_search_service.py, line 151-210

def _search_all_methods(self, query: str) -> List[AgentIntent]:

   ```python
    # All three methods run in parallel

    keyword_results = self.registry_client.search_by_keywords(query)

    pattern_results = self.registry_client.search_by_utterance_patterns(query)

    embedding_results = self.registry_client.search_by_embedding_similarity(query)

    # Results are combined and deduplicated

   ```
### Important: policies.json is not used for intent identification

The policies.json file is not used to identify intents. It is used after the intent is identified:

1. Intent identification: user query → search methods → identify policy/policyqa intent

2. Intent execution: policy_qa_activity tool loads policies.json → passes all policies to LLM → LLM answers the question using the policies

From policy_qa.py:

- The tool loads all policies from policies.json

- Creates a prompt with all policies

- Uses an LLM to answer the question based on the provided policies

### Summary

- Intent identification: hybrid (keyword + regex + semantic search)

- policies.json usage: not for intent identification; used during execution to answer policy questions via LLM

This hybrid approach improves recall by combining exact keyword matches, pattern matching, and semantic similarity.
