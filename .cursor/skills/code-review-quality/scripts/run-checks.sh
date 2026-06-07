#!/usr/bin/env bash
# Run quality checks for the current repo. Detects stack and invokes the right tooling.
set -uo pipefail

cd "$(git rev-parse --show-toplevel)"

EXIT=0
echo "==> Code Quality Checks"

run() {
  local name=$1; shift
  echo "--- $name"
  if "$@"; then
    echo "    [PASS] $name"
  else
    echo "    [FAIL] $name"
    EXIT=1
  fi
}

# Prefer the project Makefile if present
if [ -f Makefile ] && grep -q '^quality:' Makefile; then
  make quality
  exit $?
fi

# Python
if [ -f pyproject.toml ] || compgen -G "**/*.py" >/dev/null; then
  command -v ruff >/dev/null && run "ruff" ruff check .
  command -v mypy >/dev/null && [ -f pyproject.toml ] && run "mypy" mypy --strict src 2>/dev/null || true
  command -v pytest >/dev/null && run "pytest+coverage" pytest --cov --cov-report=xml -q
fi

# TypeScript / JavaScript
if [ -f package.json ]; then
  if command -v pnpm >/dev/null; then PM=pnpm
  elif command -v npm >/dev/null; then PM=npm
  else PM=""; fi
  if [ -n "$PM" ]; then
    grep -q '"lint"' package.json && run "lint" $PM run lint
    grep -q '"typecheck"' package.json && run "typecheck" $PM run typecheck
    grep -q '"test"' package.json && run "test+coverage" $PM run test -- --coverage --run 2>/dev/null || true
  fi
fi

# JVM (Gradle)
if [ -f gradlew ]; then
  run "gradle test+jacoco" ./gradlew test jacocoTestReport --no-daemon
fi

# JVM (Maven)
if [ -f pom.xml ]; then
  run "maven verify" mvn -q verify
fi

# Diff-coverage gate
if command -v diff-cover >/dev/null; then
  for report in coverage.xml coverage/cobertura-coverage.xml build/reports/jacoco/test/jacocoTestReport.xml target/site/jacoco/jacoco.xml; do
    if [ -f "$report" ]; then
      run "diff-cover $report" diff-cover "$report" --compare-branch=origin/main --fail-under=80
      break
    fi
  done
else
  echo "    [WARN] diff-cover not installed — coverage gate skipped"
fi

# Duplication (jscpd)
if command -v npx >/dev/null; then
  run "jscpd duplication <= 3%" bash -c 'npx -y jscpd@4 --threshold 3 --silent --gitignore . 2>/dev/null'
fi

# Security (semgrep)
if command -v semgrep >/dev/null; then
  run "semgrep security-audit" semgrep --config=p/security-audit --config=p/secrets --error --quiet .
else
  echo "    [WARN] semgrep not installed — security scan skipped (pip install semgrep)"
fi

# Cognitive complexity (Python: xenon; TS: enforced via eslint-plugin-sonarjs in lint step)
if [ -f pyproject.toml ] && command -v xenon >/dev/null; then
  run "xenon cognitive complexity" xenon --max-absolute B --max-modules A --max-average A src
fi

if [ $EXIT -ne 0 ]; then
  echo ""
  echo "==> One or more checks FAILED"
fi
exit $EXIT
