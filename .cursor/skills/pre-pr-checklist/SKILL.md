---
name: pre-pr-checklist
description: Run the full quality gate locally and produce a PR-readiness report before pushing or opening a pull request. Use before git push, before opening a PR, or when the user asks "is this ready to ship", "open a PR", or "run the checklist".
---

# Pre-PR Checklist

## When to invoke

- Before `git push` to a feature branch.
- Before `gh pr create`.
- When user asks "is this ready?", "ship it", "open PR".

## Workflow

```
- [ ] 1. Verify branch and base
- [ ] 2. Run lint + typecheck
- [ ] 3. Run tests with coverage
- [ ] 4. Run diff-coverage gate (>= 80%)
- [ ] 5. Run complexity check
- [ ] 6. Run security scan
- [ ] 7. Produce readiness report
- [ ] 8. Fix any gaps and re-verify
```

### Step 1: Branch + base

```bash
git fetch origin
git status
git rev-parse --abbrev-ref HEAD
git log origin/main..HEAD --oneline
```

Confirm: branch is up to date with `origin/main`, no merge conflicts, commits look clean.

### Step 2-6: Run the gate

```bash
bash scripts/check-pr.sh
```

The script:
1. Runs language-appropriate lint (ruff / biome / ktlint).
2. Runs typecheck (mypy --strict / tsc --noEmit / no-op for compiled JVM).
3. Runs tests with coverage (pytest / vitest / gradle test).
4. Runs `diff-cover --fail-under=80` against `origin/main`.
5. Runs complexity check (radon / eslint-plugin-sonarjs / detekt).
6. Runs security scan (bandit / npm audit / spotbugs).

### Step 7: Readiness report

Produce this table:

```markdown
| Check | Result | Detail |
|-------|--------|--------|
| Lint | PASS | 0 violations |
| Typecheck | PASS | strict mode |
| Tests | PASS | 142 passed |
| Coverage (changed lines) | PASS | 87.3% line, 74.1% branch |
| Coverage (per-file floor) | PASS | min 64% (src/foo.py) |
| Cognitive complexity | PASS | max 12 (was 11) |
| Security scan | PASS | 0 high/critical |
| Secrets scan | PASS | clean |

Status: READY
```

### Step 8: Gaps

If any check fails, do NOT open the PR. Fix and re-run from step 2.

For coverage gaps, invoke the `write-validation-tests` skill.
For complexity violations, invoke the `refactor-for-complexity` skill.

## PR Description Template

Use this when opening the PR:

```markdown
## Summary
<1-3 bullets describing what changed and why>

## Quality gate (local)
- Lint: PASS
- Typecheck: PASS
- Tests: <N> passed
- Coverage on new code: <line>% line / <branch>% branch (target: 80%/70%)
- Cognitive complexity: max <N> (target: <= 15)
- Security: <N> high/critical (target: 0)

## Risk
<low/medium/high>, with one-line justification

## Test plan
- [ ] Manual verification steps reviewer should run
```
