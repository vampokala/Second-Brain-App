# Quality Soft Launch — Second-Brain-App

This repo uses the [engineering-standards](https://github.com/CHANGEME-ORG/engineering-standards) toolkit for AI-assisted code quality. During **soft launch**, gates **report** findings but do **not block** commits or merges.

## One-time setup

From the repo root:

```bash
# 1. Install Python quality tools
pip install -r requirements/quality.txt

# 2. Install frontend deps (includes eslint-plugin-sonarjs + vitest coverage)
cd frontend && npm install && cd ..

# 3. Install pre-commit (fast hooks only — no blocking pre-push gates yet)
pre-commit install --hook-type pre-commit --hook-type commit-msg

# 4. Optional: detect-secrets baseline (first run)
detect-secrets scan > .secrets.baseline 2>/dev/null || true

# 5. Restart Cursor (loads .cursor/rules, .cursor/hooks.json, skills)
```

Or use Make:

```bash
make quality-install
```

## Verify it works

```bash
make quality-soft
```

You should see a report with PASS / WARN / FAIL sections. Exit code is **0** during soft launch (unless you pass `--strict`).

In Cursor:
1. Open **Settings → Hooks** — confirm `lint-on-edit`, `gate-git-commit`, `quality-loop` are loaded.
2. Open **Rules** — confirm `quality-baseline`, `tests-required`, `python-quality`, `typescript-quality` appear.
3. Edit a `.py` file with a lint issue — agent should receive lint feedback on save.

## What runs where (soft launch)

| Layer | Active? | Blocks? |
|-------|---------|---------|
| `.cursor/rules/*.mdc` | Yes | No (guidance) |
| `.cursor/skills/*` | Yes | No |
| `.cursor/hooks` lint-on-edit | Yes | No |
| `.cursor/hooks` gate-git-commit | Yes | **Warn only** (`soft_launch: true`) |
| `pre-commit` (commit stage) | Yes | Yes for format/lint on staged files |
| `pre-commit` (pre-push stage) | Not installed yet | — |
| GitHub `quality-soft.yml` | Yes on PRs | **No** (`continue-on-error`) |
| GitHub `ci.yml` | Yes | Yes (existing checks) |

## Coverage targets (already configured)

- Python: `coverage.xml`, `fail_under = 80` in `pyproject.toml`
- TypeScript: Vitest thresholds 80% line / 70% branch in `frontend/vite.config.ts`
- PR diff gate: `diff-cover --fail-under=80` (advisory until hard launch)

## Optional: Qlty dashboard (free ≤5 users)

1. Sign up at https://qlty.sh and install the GitHub App.
2. Config is in `.qlty/qlty.toml`.
3. Qlty posts PR comments and trends — **does not block merge**.

## Graduating to hard launch (week 3+)

1. Fix top warnings from `make quality-soft` and PR `quality-soft` artifacts.
2. Set in `.quality.yml`:
   ```yaml
   soft_launch: false
   ```
3. Install pre-push hooks:
   ```bash
   pre-commit install --install-hooks
   ```
4. Enable blocking workflow in `.github/workflows/quality.yml` (uncomment triggers).
5. Run drill: `make quality-soft` with `./scripts/quality-soft.sh --strict` — must pass.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Hooks not in Cursor Settings | Ensure `.cursor/hooks.json` exists (not only `hooks/hooks.json`). Restart Cursor. |
| Rules not visible | `.cursor/rules/` must not be gitignored (see `.gitignore` exceptions). |
| `ruff`/`semgrep` not found | `pip install -r requirements/quality.txt` |
| Frontend lint fails on sonarjs | `cd frontend && npm install` |
| Vitest coverage fails thresholds | Expected during soft launch — add tests or lower thresholds temporarily with a ticket |

## Re-bootstrap from engineering-standards

```bash
make quality-bootstrap
```
