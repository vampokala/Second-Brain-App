Go ahead and delete it now. Here's the full workflow:

## Step 1: Delete `general/ack` Now

curl -X DELETE http://localhost:8000/intent/general/ack

## Step 2: Re-register When You Switch to the Other Workspace

When you're ready to work with the workspace that owns `general/ack`, just run the same registration script from that workspace:

cd <other-workspace-root>

python3 scripts/register_intents.py \

--api-url http://localhost:8000 \

--deploy-env local \

--intent general/ack

That will upsert it back into the registry with the correct `executor_service_name` for that worker.

If that workspace uses a different `routing.base` than `centralwork-testworker`, you'll also need to make sure a matching Nexus endpoint exists in Temporal UI (`http://localhost:8080` -> Nexus Endpoints) pointing to that worker's namespace and task queue.

## Quick Reference: Full Re-registration Checklist

1. Start orchestrator infra (if not already running)
2. Start the other worker stack (`docker compose up`)
3. Register the Temporal namespace for that worker (if not already done):
    
    docker exec temporal tctl --address temporal:7233 \
    
    --ns <worker-namespace> namespace register --rd 3
    
4. Create/verify Nexus endpoint in Temporal UI matching that worker's routing
5. Register the intent:
    
    python3 scripts/register_intents.py \
    
    --api-url http://localhost:8000 \
    
    --deploy-env local \
    
    --intent general/ack
    

The intent registry is just a Postgres DB -- registrations persist across container restarts but not across `docker compose down -v`. So you only need to re-register if you've wiped the volumes or explicitly deleted the intent.