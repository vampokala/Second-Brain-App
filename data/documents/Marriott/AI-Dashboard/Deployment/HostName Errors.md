Issue: Container CrashLoopBackOff — `mi-tec` rejects `--host` flag

Environment: EKS cluster `mi-lz-eks-shared-dev`, namespace `emergingtech-tipai-dev3` Image: `artifactory.marriott.com/emergingtech/emergingtech-tipai-ecmp-dashboard:feature-ai-dashboard-sync-6ca9869-1309` Harness Pipeline: CICD #1309

Symptom: Pod `emergingtech-tipai-ecmp-dashboard-mi-microservice` enters `CrashLoopBackOff` immediately after startup. Container logs show:

Error: unknown flag: --host

Usage:

mi-tec [flags] [[Chained_Process]]

time="2026-04-15T14:12:23Z" level=error msg="unknown flag: --host"

Root Cause: The base image `artifactory.marriott.com/base-images/python:3.10` has `mi-tec` (Marriott template engine) set as the `ENTRYPOINT`. The Dockerfile only defined a `CMD`:

CMD ["uvicorn", "src.adapters.inbound.server:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "debug"]

At runtime, Docker concatenates `ENTRYPOINT` + `CMD`, producing:

mi-tec uvicorn src.adapters.inbound.server:app --host 0.0.0.0 --port 8080 --log-level debug

`mi-tec` attempted to parse `--host` as its own flag, failed, and exited with an error. This caused the container to crash on every restart.

Resolution: Added `ENTRYPOINT []` to the Dockerfile to clear the inherited entrypoint from the base image, allowing the `CMD` to execute directly:

ENTRYPOINT []

CMD ["uvicorn", "src.adapters.inbound.server:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "debug"]

This is safe because the Python/FastAPI app reads configuration from environment variables (Vault-injected secrets via `envFrom`) and does not rely on `mi-tec` template processing.

Verification: Tested locally with `docker run` — confirmed CMD runs directly without `mi-tec` interception.