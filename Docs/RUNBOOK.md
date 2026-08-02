# RUNBOOK

## 1. Build + Launch UI

Use either direct Docker commands or Make targets.

Docker commands:
```bash
docker compose build
docker compose up -d
```

Make commands:
```bash
make build
make up
```

Launch UI:
```bash
open http://localhost:8000
```

## 2. Daily Commands

```bash
make up
make down
make restart
make status
make logs
```

## 3. Health + Smoke

```bash
curl -s http://localhost:8000/health
make smoke
```

Expected: health returns `status: ok` and smoke checks pass all endpoints.

## 4. Ingest Operations

- Trigger full rebuild: `make reindex`
- Watch ingest events: `curl -N http://localhost:8000/events/ingest`
- Validate vault stats: `curl -s http://localhost:8000/vault/stats`

## 5. Database Operations

Open SQL shell:
```bash
make dbshell
```

Useful SQL:
```sql
SELECT count(*) FROM document_chunks;
SELECT count(*) FROM chats;
SELECT * FROM embed_queue WHERE status='pending';
SELECT * FROM ingest_events ORDER BY created_at DESC LIMIT 20;
SELECT key FROM app_settings ORDER BY key;
```

Run migrations:
```bash
make migrate
```

## 6. Backup / Restore

Manual backup:
```bash
make backup
```

Automated backup: launchd job runs daily at 03:00.

Restore:
```bash
make down
make up
# wait until postgres healthy
gunzip -c backups/secondbrain-YYYY-MM-DD.sql.gz | docker compose exec -T postgres psql -U secondbrain secondbrain
```

## 7. Model Management

```bash
docker compose exec ollama ollama list
docker compose exec ollama ollama pull llama3.1:8b
docker compose exec ollama ollama pull nomic-embed-text
docker compose exec ollama ollama rm <model>
```

## 8. Provider Key Rotation

- Env key path: update `.env`, then `make restart`.
- Runtime key path: `PATCH /settings` with new key payload.
- Verify enabled providers: `GET /config/llm`.

## 9. Log Locations

- API logs: `make logs`
- launchd app logs:
  - `~/Library/Logs/second-brain-app.out.log`
  - `~/Library/Logs/second-brain-app.err.log`
- launchd backup logs:
  - `~/Library/Logs/second-brain-backup.log`

## 10. Disk Usage Monitoring

```bash
docker system df
du -sh backups/
df -h
```

If disk pressure appears, prune unused Docker resources and archive old backups.

## 11. Watcher Troubleshooting

Checklist:
1. Ensure vault host path exists and is mounted to `/vault`.
2. Confirm `WATCHER_DEBOUNCE_MS` is not overly high.
3. Check API logs for watcher exceptions.
4. Drop a tiny file into `raw/` and monitor `/events/ingest`.

## 12. Performance Tuning

- Increase `MAX_INGEST_WORKERS` for fast multi-core ingest.
- Reduce it if CPU contention or memory pressure occurs.
- Increase `OLLAMA_KEEP_ALIVE` to reduce model reloads.
- Use smaller chat models under low-memory conditions.

## 13. launchd Install / Remove

Install:
```bash
make install-launchd
launchctl list | rg secondbrain
```

Uninstall:
```bash
make uninstall-launchd
```
