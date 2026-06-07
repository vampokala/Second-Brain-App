# Verification Query Suite

Use this regression suite after major retrieval/ingest changes.

## Pass Criteria

For each query:
1. At least 3 relevant citations (where applicable).
2. Sources resolve in Vault browser without 404.
3. Response is grounded in retrieved evidence.

## Query Matrix

| # | Query | Expected Source Region |
|---|---|---|
| 1 | What is hybrid retrieval and how is it used in my Doc-Ingestion project? | `raw/AI-Projects/Document-Ingestion/` |
| 2 | Summarize my Marriott TIP AI Codebase architecture in one paragraph | `raw/Vamshi-KnowledgeBase/Marriott/AI-Dashboard/` |
| 3 | What roles am I tracking in my career command center? | `raw/Daily-Job-Scan/`, `raw/Interview-Prep/` |
| 4 | How does subquadratic selective attention differ from standard transformer attention? | `raw/Learning/...SubQ...` |

## Execution Steps

1. Ensure stack is up: `make up`
2. Ensure models available in Ollama.
3. Run full reindex: `make reindex`
4. Execute the four queries in Chat UI.
5. Record results using template below.

## Result Template

```text
Date:
Build/Commit:
Model:

Q1: PASS/FAIL
- citations:
- notes:

Q2: PASS/FAIL
- citations:
- notes:

Q3: PASS/FAIL
- citations:
- notes:

Q4: PASS/FAIL
- citations:
- notes:

Overall: PASS/FAIL
Actions:
```

## Watcher and Degradation Checks

### Watcher
```bash
echo "# Watcher Test" > ~/Documents/Second-Brain/raw/Tests/p9-verify.md
curl -N http://localhost:8000/events/ingest
```
Expect ingest event sequence and vault/wiki updates.

### Ollama degradation
```bash
docker compose stop ollama
echo "# Degradation Test" > ~/Documents/Second-Brain/raw/Tests/degrade-test.md
docker compose exec postgres psql -U secondbrain secondbrain -c "SELECT * FROM embed_queue WHERE status='pending';"
docker compose start ollama
```
Expect pending queue rows when down, then drain on recovery.
