#!/bin/bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/Users/vamshipokala/Documents/Second-Brain-App/backups}"
COMPOSE_FILE="${COMPOSE_FILE:-/Users/vamshipokala/Documents/Second-Brain-App/docker-compose.yml}"

mkdir -p "$BACKUP_DIR"
echo "[$(date)] Starting pg_dump backup..."

docker compose -f "$COMPOSE_FILE" exec -T postgres \
    pg_dump -U secondbrain secondbrain \
    | gzip > "$BACKUP_DIR/secondbrain-$(date +%Y-%m-%d).sql.gz"

find "$BACKUP_DIR" -name "*.sql.gz" -mtime +7 -delete

echo "[$(date)] Backup complete."
ls -lh "$BACKUP_DIR"/*.sql.gz 2>/dev/null || echo "  (none)"
