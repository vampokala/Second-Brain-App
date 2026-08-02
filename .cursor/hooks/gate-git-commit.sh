#!/usr/bin/env bash
# beforeShellExecution: gate `git commit` / `git push` via pre-commit + diff-cover.
# Respects .quality.yml soft_launch: true -> warn (ask) instead of deny.
set -uo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.command // empty')

is_soft_launch() {
  if [ -f .quality.yml ]; then
    grep -qE '^soft_launch:\s*true' .quality.yml 2>/dev/null && return 0
  fi
  if [ -f .quality.yaml ]; then
    grep -qE '^soft_launch:\s*true' .quality.yaml 2>/dev/null && return 0
  fi
  return 1
}

deny_or_warn() {
  local msg=$1
  if is_soft_launch; then
    jq -n --arg msg "[SOFT LAUNCH] Quality checks reported issues (not blocking):

$msg

Fix before hard launch. Run: make quality-soft" \
      '{permission: "ask", agent_message: $msg, user_message: "Soft launch: quality issues found. You may proceed, but please fix soon."}'
  else
    jq -n --arg msg "$msg" \
      '{permission: "deny", agent_message: $msg, user_message: "Quality gate blocked this command."}'
  fi
}

if [ -z "$COMMAND" ]; then
  echo '{"permission": "allow"}'
  exit 0
fi

if ! echo "$COMMAND" | grep -qE 'git\s+(commit|push)'; then
  echo '{"permission": "allow"}'
  exit 0
fi

if echo "$COMMAND" | grep -qE -- '--no-verify'; then
  jq -n '{
    permission: "ask",
    user_message: "Agent is attempting to bypass pre-commit hooks (--no-verify). Approve?",
    agent_message: "Use --no-verify only when explicitly authorized by the user."
  }'
  exit 0
fi

# Soft launch: only run fast pre-commit hooks (skip pre-push stage hooks)
if [ -f .pre-commit-config.yaml ] && command -v pre-commit >/dev/null 2>&1; then
  if is_soft_launch; then
    OUTPUT=$(pre-commit run 2>&1) || RC=$?
  else
    OUTPUT=$(pre-commit run --hook-stage pre-push 2>&1; pre-commit run 2>&1) || RC=$?
  fi
  RC=${RC:-0}

  if [ $RC -ne 0 ]; then
    SUMMARY=$(echo "$OUTPUT" | tail -30)
    deny_or_warn "Pre-commit checks failed.

$SUMMARY

Fix the issues above, then re-run."
    exit 0
  fi
fi

if [ -f .quality.yml ] || [ -f .quality.yaml ]; then
  THRESHOLD=$(grep -E '^coverage_threshold' .quality.y*ml 2>/dev/null | awk '{print $2}' | head -1)
  THRESHOLD=${THRESHOLD:-80}

  COVERAGE_FILE=""
  for f in coverage.xml coverage/cobertura-coverage.xml; do
    [ -f "$f" ] && COVERAGE_FILE="$f" && break
  done

  if [ -n "$COVERAGE_FILE" ] && command -v diff-cover >/dev/null 2>&1; then
    DC_OUT=$(diff-cover "$COVERAGE_FILE" --compare-branch=origin/main --fail-under="$THRESHOLD" 2>&1) || DC_RC=$?
    DC_RC=${DC_RC:-0}
    if [ $DC_RC -ne 0 ]; then
      SUMMARY=$(echo "$DC_OUT" | tail -20)
      deny_or_warn "Coverage below threshold (${THRESHOLD}%).

$SUMMARY

Add tests for uncovered lines."
      exit 0
    fi
  fi
fi

echo '{"permission": "allow"}'
exit 0
