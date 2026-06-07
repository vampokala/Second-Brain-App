#!/usr/bin/env bash
# Full PR-readiness check. Runs lint, typecheck, tests, coverage gate, complexity, security.
set -uo pipefail

cd "$(git rev-parse --show-toplevel)"

BASE_BRANCH="${BASE_BRANCH:-origin/main}"
COVERAGE_THRESHOLD="${COVERAGE_THRESHOLD:-80}"
FAILURES=()

check() {
  local name=$1; shift
  echo ""
  echo "==> $name"
  if "$@"; then
    echo "    [PASS] $name"
  else
    echo "    [FAIL] $name"
    FAILURES+=("$name")
  fi
}

# Detect stacks
HAS_PY=0; HAS_TS=0; HAS_GRADLE=0; HAS_MVN=0
[ -f pyproject.toml ] || compgen -G "**/*.py" >/dev/null 2>&1 && HAS_PY=1
[ -f package.json ] && HAS_TS=1
[ -f gradlew ] && HAS_GRADLE=1
[ -f pom.xml ] && HAS_MVN=1

# Lint
if [ $HAS_PY -eq 1 ] && command -v ruff >/dev/null; then
  check "ruff lint" ruff check .
fi
if [ $HAS_TS -eq 1 ]; then
  PM=$(command -v pnpm >/dev/null && echo pnpm || (command -v npm >/dev/null && echo npm))
  if [ -n "$PM" ] && grep -q '"lint"' package.json; then
    check "ts lint" $PM run lint
  fi
fi
if [ $HAS_GRADLE -eq 1 ]; then
  check "gradle lint" ./gradlew ktlintCheck detekt --no-daemon 2>/dev/null || true
fi

# Typecheck
if [ $HAS_PY -eq 1 ] && command -v mypy >/dev/null && [ -d src ]; then
  check "mypy --strict" mypy --strict src
fi
if [ $HAS_TS -eq 1 ]; then
  PM=$(command -v pnpm >/dev/null && echo pnpm || (command -v npm >/dev/null && echo npm))
  if [ -n "$PM" ] && grep -q '"typecheck"' package.json; then
    check "tsc" $PM run typecheck
  fi
fi

# Tests + coverage
COVERAGE_FILE=""
if [ $HAS_PY -eq 1 ] && command -v pytest >/dev/null; then
  check "pytest + coverage" pytest --cov --cov-report=xml -q
  [ -f coverage.xml ] && COVERAGE_FILE="coverage.xml"
fi
if [ $HAS_TS -eq 1 ]; then
  PM=$(command -v pnpm >/dev/null && echo pnpm || (command -v npm >/dev/null && echo npm))
  if [ -n "$PM" ] && grep -q '"test"' package.json; then
    check "vitest/jest + coverage" $PM run test -- --coverage --run 2>/dev/null || true
    [ -f coverage/cobertura-coverage.xml ] && COVERAGE_FILE="coverage/cobertura-coverage.xml"
  fi
fi
if [ $HAS_GRADLE -eq 1 ]; then
  check "gradle test + jacoco" ./gradlew test jacocoTestReport --no-daemon
  [ -f build/reports/jacoco/test/jacocoTestReport.xml ] && COVERAGE_FILE="build/reports/jacoco/test/jacocoTestReport.xml"
fi
if [ $HAS_MVN -eq 1 ]; then
  check "maven verify" mvn -q verify
  [ -f target/site/jacoco/jacoco.xml ] && COVERAGE_FILE="target/site/jacoco/jacoco.xml"
fi

# Diff-coverage gate (cross-stack)
if [ -n "$COVERAGE_FILE" ] && command -v diff-cover >/dev/null; then
  check "diff-cover (>= ${COVERAGE_THRESHOLD}%)" diff-cover "$COVERAGE_FILE" --compare-branch="$BASE_BRANCH" --fail-under="$COVERAGE_THRESHOLD"
elif [ -n "$COVERAGE_FILE" ]; then
  echo "    [WARN] diff-cover not installed (pip install diff-cover) — coverage gate skipped"
fi

# Complexity — cyclomatic (radon) + cognitive (xenon)
if [ $HAS_PY -eq 1 ] && command -v radon >/dev/null; then
  check "radon cyclomatic (<= C)" bash -c "radon cc src -n D -s | grep -E '^\s+.*\([0-9]+\)' && exit 1 || exit 0"
fi
if [ $HAS_PY -eq 1 ] && command -v xenon >/dev/null; then
  check "xenon cognitive (max-absolute B)" xenon --max-absolute B --max-modules A --max-average A src
fi

# Security: bandit + semgrep + npm audit
if [ $HAS_PY -eq 1 ] && command -v bandit >/dev/null; then
  check "bandit" bandit -q -r src -ll
fi
if command -v semgrep >/dev/null; then
  check "semgrep security-audit" semgrep --config=p/security-audit --config=p/secrets --error --quiet .
fi
if [ $HAS_TS -eq 1 ]; then
  PM=$(command -v pnpm >/dev/null && echo pnpm || (command -v npm >/dev/null && echo npm))
  [ -n "$PM" ] && check "audit" $PM audit --audit-level=high
fi

# Duplication (jscpd, cross-stack)
if command -v npx >/dev/null; then
  check "jscpd duplication <= 3%" bash -c 'npx -y jscpd@4 --threshold 3 --silent --gitignore . 2>/dev/null'
fi

# Secrets
if command -v detect-secrets >/dev/null && [ -f .secrets.baseline ]; then
  check "detect-secrets" detect-secrets-hook --baseline .secrets.baseline $(git diff --name-only "$BASE_BRANCH"...HEAD 2>/dev/null)
fi

# Summary
echo ""
echo "================================================================"
if [ ${#FAILURES[@]} -eq 0 ]; then
  echo "STATUS: READY FOR PR"
  exit 0
else
  echo "STATUS: NOT READY — ${#FAILURES[@]} check(s) failed:"
  for f in "${FAILURES[@]}"; do echo "  - $f"; done
  exit 1
fi
