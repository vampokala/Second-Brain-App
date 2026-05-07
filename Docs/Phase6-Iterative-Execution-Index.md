# Phase 6 Iterative Execution Index

Use this index to execute Phase 6 one plan at a time while keeping the master plan unchanged.

Master plan:
- `Docs/Phase6-RefactorDemo_React.md`

Execution order:
1. `Docs/Phase6.1-Backend-Session-Isolation-Plan.md`
2. `Docs/Phase6.2-React-MVP-Plan.md`
3. `Docs/Phase6.3-Container-Cutover-Plan.md`
4. `Docs/Phase6.4-Streamlit-Decommission-Plan.md` (optional)

## Phase gate rule

Do not start the next phase until current phase:
- meets all exit criteria,
- passes phase verification commands,
- and has handoff artifacts ready for the next phase.

## Shared constraints (apply to all phase files)

- Knowledge scope stays `global|session|both`.
- Guardrails stay at defaults unless explicitly tuned via `DOC_DEMO_*` env:
  - 3 files/session
  - 3 MB/file
  - 8 MB/session
  - 30 min idle TTL
- Keep rollback notes current during 6.3 and 6.4.
