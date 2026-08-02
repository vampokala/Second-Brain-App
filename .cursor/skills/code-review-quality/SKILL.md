---
name: code-review-quality
description: Self-review a code diff against SonarQube-grade quality criteria before declaring a task done. Use when finishing an implementation task, before opening a PR, or when the user asks for a code review, quality check, or pre-merge audit.
---

# Code Review Quality

## When to invoke

- Before declaring an implementation task complete.
- Before running `git commit` or opening a PR.
- When the user asks "review my changes" / "check quality" / "is this ready?"

## Workflow

Copy this checklist and track progress:

```
- [ ] Step 1: Capture the diff
- [ ] Step 2: Run automated checks
- [ ] Step 3: Manual review pass
- [ ] Step 4: Produce findings table
- [ ] Step 5: Apply fixes
- [ ] Step 6: Re-verify
```

### Step 1: Capture the diff

```bash
git diff origin/main...HEAD --stat
git diff origin/main...HEAD
```

### Step 2: Run automated checks

```bash
bash scripts/run-checks.sh
```

This runs the project's `make quality` target (lint + typecheck + test + coverage + complexity). If `make quality` doesn't exist, fall back to the per-stack commands documented in `pre-pr-checklist`.

### Step 3: Manual review pass

For each changed file, check against criteria:

**Correctness**
- Edge cases handled (null, empty, max, min, concurrent, error)
- Invariants documented and enforced

**Cognitive complexity** (SonarQube criterion)
- Each function ≤ 15 cognitive complexity
- Nesting depth ≤ 3
- Function length ≤ 60 lines

**Error handling**
- No swallowed exceptions
- Errors carry context (IDs, operation name)
- Typed exceptions, not bare `Exception` / `Error`

**Security**
- No hard-coded secrets
- External input validated
- SQL/shell args parameterized

**Tests**
- New/changed lines covered ≥ 80% (line) / ≥ 70% (branch)
- Tests assert behavior not implementation
- Error paths covered

### Step 4: Produce findings table

```markdown
| Severity | File:Line | Issue | Suggested Fix |
|----------|-----------|-------|---------------|
| Critical | src/auth.py:42 | Bare `except` swallows token errors | Catch `JWTError`, re-raise as `AuthError` with context |
| Major    | src/api.ts:88 | Cognitive complexity 19 in `processOrder` | Extract `validateOrder` and `chargeOrder`; use guard clauses |
| Minor    | src/api.ts:120 | Missing JSDoc for public function | Add doc with `@throws` |
```

Severity scale:
- **Critical**: must fix before merge (security, correctness, swallowed errors, data loss)
- **Major**: must fix before merge (complexity threshold, missing tests, type safety hole)
- **Minor**: should fix or open a follow-up ticket (style, naming, docs)

### Step 5: Apply fixes

Fix Critical and Major before declaring done. For Minor items, either fix now or list as follow-up.

### Step 6: Re-verify

Re-run `bash scripts/run-checks.sh`. Only declare done when:
- All automated checks pass
- No Critical or Major findings remain
- Coverage on changed lines is ≥ 80% / ≥ 70%

## Output Format

End your review with:

```
Review summary:
- Files reviewed: N
- Critical: 0 (was X, all fixed)
- Major: 0 (was Y, all fixed)
- Minor: Z (Z opened as follow-ups: TICKET-1, TICKET-2)
- Coverage on new code: 87% line / 74% branch
- Cognitive complexity max: 12
- Status: READY FOR PR
```

If status is not READY, list the remaining blockers.
