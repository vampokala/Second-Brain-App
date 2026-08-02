#!/usr/bin/env bash
# Soft-launch quality report: runs all gates, prints summary, exits 0 unless --strict.
# Usage:
#   ./scripts/quality-soft.sh          # report only (soft launch)
#   ./scripts/quality-soft.sh --strict # exit 1 on any failure (hard launch drill)
set -uo pipefail

cd "$(git rev-parse --show-toplevel)"
STRICT=0
[ "${1:-}" = "--strict" ] && STRICT=1

FAILURES=()
WARNINGS=()

run_check() {
  local name=$1
  shift
  echo ""
  echo "==> $name"
  if "$@"; then
    echo "    [PASS] $name"
  else
    echo "    [FAIL] $name"
    FAILURES+=("$name")
  fi
}

run_warn() {
  local name=$1
  shift
  echo ""
  echo "==> $name (advisory during soft launch)"
  if "$@"; then
    echo "    [PASS] $name"
  else
    echo "    [WARN] $name"
    WARNINGS+=("$name")
  fi
}

echo "Second-Brain-App quality soft launch"
echo "Config: $(grep soft_launch .quality.yml 2>/dev/null || echo 'soft_launch: unknown')"
echo ""

# Python
if command -v ruff >/dev/null; then
  run_check "ruff lint" ruff check src tests
else
  echo "[SKIP] ruff not installed (pip install -r requirements/quality.txt)"
fi

if command -v mypy >/dev/null; then
  run_warn "mypy" mypy src --ignore-missing-imports
fi

if command -v bandit >/dev/null; then
  run_check "bandit" bandit -q -ll -r src
fi

if command -v xenon >/dev/null; then
  run_warn "xenon cognitive complexity" xenon --max-absolute B --max-modules A --max-average A src
fi

if command -v pytest >/dev/null; then
  run_warn "pytest + coverage" pytest tests/unit/ --cov=src --cov-report=xml --cov-branch -q
fi

# Frontend
if [ -f frontend/package.json ]; then
  (
    cd frontend
    if [ -d node_modules ]; then
      run_check "eslint + sonarjs" npm run lint
      run_check "tsc" npm run typecheck
      run_warn "vitest + coverage" npm run test:coverage
    else
      echo "[SKIP] frontend: run 'cd frontend && npm ci' first"
    fi
  )
fi

# Cross-stack (advisory in soft launch)
if command -v semgrep >/dev/null; then
  run_warn "semgrep security" semgrep --config=p/security-audit --config=p/secrets --error --quiet .
fi

if command -v npx >/dev/null; then
  run_warn "jscpd duplication" bash -c 'npx -y jscpd@4 --threshold 3 --silent --gitignore . 2>/dev/null'
fi

THRESHOLD=$(grep -E '^coverage_threshold' .quality.yml 2>/dev/null | awk '{print $2}')
THRESHOLD=${THRESHOLD:-80}
if command -v diff-cover >/dev/null && [ -f coverage.xml ]; then
  run_warn "diff-cover (>= ${THRESHOLD}%)" diff-cover coverage.xml --compare-branch=origin/main --fail-under="$THRESHOLD"
elif [ -f coverage.xml ]; then
  echo "[SKIP] diff-cover not installed"
fi

# Summary
echo ""
echo "================================================================"
echo "QUALITY SOFT LAUNCH REPORT"
echo "================================================================"
if [ ${#FAILURES[@]} -eq 0 ] && [ ${#WARNINGS[@]} -eq 0 ]; then
  echo "Status: ALL CHECKS PASSED"
elif [ ${#FAILURES[@]} -eq 0 ]; then
  echo "Status: PASS WITH WARNINGS (${#WARNINGS[@]})"
  printf '  - %s\n' "${WARNINGS[@]}"
else
  echo "Status: NEEDS ATTENTION"
  echo "Failures (${#FAILURES[@]}):"
  printf '  - %s\n' "${FAILURES[@]}"
  [ ${#WARNINGS[@]} -gt 0 ] && printf 'Warnings (%s):\n' "${#WARNINGS[@]}" && printf '  - %s\n' "${WARNINGS[@]}"
fi
echo ""
echo "Cursor: restart IDE to load .cursor/hooks.json + rules"
echo "Hard launch: set soft_launch: false in .quality.yml, then ./scripts/quality-soft.sh --strict"
echo "================================================================"

if [ $STRICT -eq 1 ] && { [ ${#FAILURES[@]} -gt 0 ] || [ ${#WARNINGS[@]} -gt 0 ]; }; then
  exit 1
fi
exit 0
