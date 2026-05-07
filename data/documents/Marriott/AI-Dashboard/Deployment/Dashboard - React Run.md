
### How to Run

Local dev (two terminals):

```make
make dev-backend    # uvicorn --reload on :8080
make dev-frontend   # vite on :3000, proxies /api to :8080
```
Docker (production-like):


```docker
make docker # builds frontend+backend, runs on :8080
```

Harness pipeline uses `Dockerfile` which now includes the frontend build stage and reads `APP_PORT` from Vault-injected env vars (defaults to 8080, matching Helm values