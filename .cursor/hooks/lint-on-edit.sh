#!/usr/bin/env bash
# afterFileEdit: run language-specific fast linter on the just-edited file.
# Returns findings as additional_context so the agent self-corrects on the next turn.
set -uo pipefail

INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.file_path // .path // empty')

if [ -z "$FILE" ] || [ ! -f "$FILE" ]; then
  echo '{}'
  exit 0
fi

FINDINGS=""
EXT="${FILE##*.}"

case "$EXT" in
  py)
    if command -v ruff >/dev/null 2>&1; then
      FINDINGS=$(ruff check --quiet --output-format=concise "$FILE" 2>&1 || true)
    fi
    ;;
  ts|tsx|js|jsx)
    if command -v biome >/dev/null 2>&1; then
      FINDINGS=$(biome lint "$FILE" 2>&1 || true)
    elif [ -f node_modules/.bin/eslint ]; then
      FINDINGS=$(./node_modules/.bin/eslint --no-eslintrc --quiet "$FILE" 2>&1 || true)
    fi
    ;;
  java)
    if command -v checkstyle >/dev/null 2>&1; then
      FINDINGS=$(checkstyle -c /google_checks.xml "$FILE" 2>&1 | head -20 || true)
    fi
    ;;
  kt|kts)
    if command -v ktlint >/dev/null 2>&1; then
      FINDINGS=$(ktlint --relative "$FILE" 2>&1 || true)
    fi
    ;;
  *)
    echo '{}'
    exit 0
    ;;
esac

FINDINGS=$(echo "$FINDINGS" | head -50)

if [ -z "$FINDINGS" ] || ! echo "$FINDINGS" | grep -qE '[a-zA-Z0-9]'; then
  echo '{}'
  exit 0
fi

jq -n --arg ctx "Lint findings for ${FILE}:
${FINDINGS}

Fix these before declaring the task done. See .cursor/rules/quality-baseline.mdc and language-specific rules." \
  '{additional_context: $ctx}'
exit 0
