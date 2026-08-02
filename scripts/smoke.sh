#!/bin/bash
set -euo pipefail

BASE="${BASE:-http://localhost:8000}"
echo "Smoke test against $BASE"

for endpoint in /health /config/llm /vault/stats /chats "/vault/files?prefix=raw/"; do
    echo -n "  $endpoint ... "
    curl -sf "$BASE$endpoint" > /dev/null && echo "OK" || echo "FAIL"
done

echo "Smoke test complete."
