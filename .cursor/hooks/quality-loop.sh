#!/usr/bin/env bash
# subagentStop: if quality checks or coverage are failing, send a followup_message
# so the subagent self-repairs. Limited to loop_limit iterations.
set -uo pipefail

INPUT=$(cat)

cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)"

if [ ! -d .git ]; then
  echo '{}'
  exit 0
fi

# Detect what's failing
FAILURES=()

# Quick lint
if [ -f pyproject.toml ] && command -v ruff >/dev/null 2>&1; then
  ruff check --quiet . >/dev/null 2>&1 || FAILURES+=("ruff lint")
fi
if [ -f package.json ] && grep -q '"lint"' package.json; then
  PM=$(command -v pnpm >/dev/null && echo pnpm || (command -v npm >/dev/null && echo npm || echo ""))
  if [ -n "$PM" ]; then
    $PM run lint >/dev/null 2>&1 || FAILURES+=("ts lint")
  fi
fi

# Coverage gate (only check if a coverage file already exists from a recent run)
for f in coverage.xml coverage/cobertura-coverage.xml; do
  if [ -f "$f" ] && command -v diff-cover >/dev/null 2>&1; then
    DC_OUT=$(diff-cover "$f" --compare-branch=origin/main --fail-under=80 2>&1) || {
      UNCOVERED=$(echo "$DC_OUT" | grep -E "^\s*-" | head -5)
      FAILURES+=("coverage < 80% on changed lines")
      COVERAGE_DETAIL="$UNCOVERED"
    }
    break
  fi
done

if [ ${#FAILURES[@]} -eq 0 ]; then
  echo '{}'
  exit 0
fi

MSG="Before stopping, these quality gates are still failing:
$(printf -- '- %s\n' "${FAILURES[@]}")
${COVERAGE_DETAIL:+
Uncovered lines:
${COVERAGE_DETAIL}
}
Fix them by:
1. Running 'bash .cursor/skills/code-review-quality/scripts/run-checks.sh'
2. For coverage gaps, invoke the write-validation-tests skill
3. For complexity issues, invoke the refactor-for-complexity skill
4. For lint issues, fix per .cursor/rules/quality-baseline.mdc"

jq -n --arg msg "$MSG" '{followup_message: $msg}'
exit 0
