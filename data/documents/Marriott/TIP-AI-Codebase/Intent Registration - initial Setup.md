| Step | Source                         | Field                   | Value                                                                   |
| ---- | ------------------------------ | ----------------------- | ----------------------------------------------------------------------- |
| 1    | `policyqa.yaml` line 144       | `routing.base`          | `ecmpwork-ecmpworker`                                                   |
| 2    | `register_intents.py` line 168 | formula                 | `{routing.base}-{DEPLOY_ENV}`                                           |
| 3    | Intent registry (DB)           | `executor_service_name` | was `enterprisechat-ecmp-worker-local`, now `ecmpwork-ecmpworker-local` |
| 4    | Temporal                       | Nexus endpoint          | `ecmpwork-ecmpworker-local`                                             |