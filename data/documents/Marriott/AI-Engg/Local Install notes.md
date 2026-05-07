
### 1. Restart Orchestrator Services

Run this command in the emergingtech-tipai-orchestrator directory:

cd emergingtech-tipai-orchestrator

docker compose -f docker/docker-compose.yml --env-file docker/.env --profile tracing up -d --build

### 2. Restart Worker Services

Run this command in the tipai-worker-template directory:

cd tipai-worker-template

docker compose -f deploy/docker-compose.yaml --env-file deploy/.env up -d --build