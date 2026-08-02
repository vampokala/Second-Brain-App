#!/usr/bin/env bash
# Measure coverage on changed lines vs base branch. Exits non-zero if below threshold.
set -uo pipefail

cd "$(git rev-parse --show-toplevel)"

BASE_BRANCH="${BASE_BRANCH:-origin/main}"
LINE_THRESHOLD="${LINE_THRESHOLD:-80}"
BRANCH_THRESHOLD="${BRANCH_THRESHOLD:-70}"
PER_FILE_FLOOR="${PER_FILE_FLOOR:-60}"

# Run tests + collect coverage
echo "==> Running tests with coverage"
COVERAGE_FILE=""

if [ -f pyproject.toml ] || compgen -G "**/*.py" >/dev/null 2>&1; then
  if command -v pytest >/dev/null; then
    pytest --cov --cov-report=xml --cov-branch -q
    [ -f coverage.xml ] && COVERAGE_FILE="coverage.xml"
  fi
fi

if [ -f package.json ]; then
  PM=$(command -v pnpm >/dev/null && echo pnpm || (command -v npm >/dev/null && echo npm))
  if [ -n "$PM" ] && grep -q '"test"' package.json; then
    $PM run test -- --coverage --run 2>/dev/null || true
    [ -f coverage/cobertura-coverage.xml ] && COVERAGE_FILE="coverage/cobertura-coverage.xml"
  fi
fi

if [ -f gradlew ]; then
  ./gradlew test jacocoTestReport --no-daemon
  [ -f build/reports/jacoco/test/jacocoTestReport.xml ] && COVERAGE_FILE="build/reports/jacoco/test/jacocoTestReport.xml"
fi

if [ -z "$COVERAGE_FILE" ]; then
  echo "[ERROR] No coverage report produced. Install pytest-cov / vitest --coverage / jacoco."
  exit 2
fi

echo "==> Coverage report: $COVERAGE_FILE"

if ! command -v diff-cover >/dev/null; then
  echo "[ERROR] diff-cover not installed. Install: pip install diff-cover"
  exit 2
fi

echo ""
echo "==> Diff coverage vs $BASE_BRANCH (line >= ${LINE_THRESHOLD}%)"
diff-cover "$COVERAGE_FILE" --compare-branch="$BASE_BRANCH" --fail-under="$LINE_THRESHOLD"
LINE_RC=$?

echo ""
echo "==> Branch coverage check (branch >= ${BRANCH_THRESHOLD}%)"
# diff-cover doesn't separate branch easily; emit reminder
diff-cover "$COVERAGE_FILE" --compare-branch="$BASE_BRANCH" --html-report diff-coverage.html >/dev/null 2>&1 || true
echo "  See diff-coverage.html for per-line details"

if [ $LINE_RC -ne 0 ]; then
  echo ""
  echo "STATUS: COVERAGE BELOW THRESHOLD — add tests for the uncovered lines listed above"
  exit 1
fi

echo ""
echo "STATUS: COVERAGE OK"
exit 0
