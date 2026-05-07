Worker
DEPLOY_ENV=local
TIPAI_APP=tipai
TIPAI_TEAM=ecmpwork
TIPAI_SERVICE=ecmp-worker

Orchestrator
DEPLOY_ENV=local
TIPAI_APP=tipai
TIPAI_TEAM=ecmporch
TIPAI_SERVICE=orchestrator


Ex:
DEPLOY_ENV=local
TIPAI_APP=tipai
TIPAI_TEAM=centralwork
TIPAI_SERVICE=testworker

Ex:
DEPLOY_ENV=local
TIPAI_APP=tipai
TIPAI_TEAM=centralorch
TIPAI_SERVICE=orchestrator


{TIPAI_APP}-{TIPAI_TEAM}-{DEPLOY_ENV}


docker exec temporal tctl --address temporal:7233 --ns tipai-centralwork-local namespace register --rd 3
docker exec temporal tctl --address temporal:7233 --ns tipai-centralorch-local namespace register --rd 3

docker exec temporal tctl --address temporal:7233 --ns tipai-ecmpwork-local namespace register --rd 3
docker exec temporal tctl --address temporal:7233 --ns tipai-ecmporch-local namespace register --rd 3


Nexus endpoint - 
ecmpwork-ecmpworker-local

Target Namepsace - tipai-ecmpwork-local
Task Queue - nexus-ecmpwork-ecmpworker-q-local

curl -s http://localhost:7243/api/v1/nexus/endpoints | python3 -m json.tool

register_intents.py 
executor_service_name = "{routing.base}-{DEPLOY_ENV}" 
                      = "ecmpwork-ecmpworker" + "-" + "local"
                      = "ecmpwork-ecmpworker-local"

