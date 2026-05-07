# Phase 6.4 Plan: Streamlit Decommission (Optional)

Source of truth: `Docs/Phase6-RefactorDemo_React.md` (this file is an execution slice for iterative delivery).
Depends on: `Docs/Phase6.3-Container-Cutover-Plan.md`

## Objective

Remove Streamlit runtime and legacy paths after React + FastAPI deployment has stabilized.

## Scope

Run only after at least one week of stable production-like behavior from Phase 6.3.

## Tasks

- Delete `src/web/streamlit_app.py`.
- Remove `streamlit` from `requirements/base.txt`.
- Remove Streamlit container from `docker/docker-compose.yml`.
- Update `README.md` screenshots and quickstart docs.
- Remove `tests/unit/test_streamlit_demo_routing.py`.
- Keep sample prompts by serving them via API (`GET /api/sample-prompts`) as shared source of truth.

## Verification

- Confirm no imports/runtime references to Streamlit remain.
- Run backend/frontend test suites and smoke checks after cleanup.
- Confirm docs and onboarding instructions match new architecture.

## Handoff (Exit Criteria)

- Streamlit code/dependencies/tests are removed cleanly.
- Docs fully reflect React + FastAPI flow.
- Sample prompts are centrally served and consumed.

## Transition to Next Program Increment

- Phase 6 closes with 6.1-6.3 complete and 6.4 executed (or intentionally deferred).
- Deferred improvements move to Phase 7 backlog.
