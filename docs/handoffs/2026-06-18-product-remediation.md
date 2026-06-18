# Product Remediation Handoff

## Goal

This session moved from readiness preparation into main-developer remediation. The MVP now has a clearer first-run path, private job workflow state, stronger evidence-centered resume review, safe export defaults, and a compatibility migration for older local SQLite databases.

## Current state

- First-run overview now shows two entry paths: stable fixture demo and private local profile workflow.
- Overview readiness cards show the job sample -> profile facts -> evidence draft flow.
- Jobs can be saved/triaged per signed-in user with status, note, and deadline.
- Job list/detail payloads include `user_status` only for the authenticated user.
- Resume evidence now includes `source_label`, `matched_terms`, and `evidence_strength`.
- Resume page shows requirement -> readable profile source -> strength -> matched terms.
- Application exports default to excluding internal gap diagnostics; diagnostic DOCX export remains explicit.
- `init_db` migrates legacy `profiles(id, ...)` and `resume_drafts(profile_id, ...)` tables to the user-scoped schema when possible, preserving unmatched legacy rows in `*_legacy` tables instead of dropping them.
- `backend/requirements.txt` remains aligned with PDF/image/OCR imports.
- The Starlette/httpx TestClient warning is resolved by installing `httpx2` in the backend dev dependency group, not in the runtime `requirements.txt` deployment list.

## Completed in this session

- Added execution plan: `docs/plans/2026-06-18-product-remediation-execution.md`.
- Added backend tests for:
  - legacy user-scoped table migration,
  - preservation of unmatched legacy SQLite rows,
  - private job status visibility,
  - invalid optional-auth token handling,
  - missing-job status deletion,
  - ISO deadline validation,
  - evidence metadata shape,
  - DOCX/PDF application vs diagnostic export behavior.
- Added frontend helper tests for:
  - onboarding paths,
  - job workflow status labels,
  - resume evidence display labels.
- Implemented `job_statuses` table and API endpoints:
  - `PUT /api/jobs/{job_id}/status`
  - `DELETE /api/jobs/{job_id}/status`
- Added frontend job status controls to `JobsPage`.
- Added overview onboarding path UI and workflow cards.
- Added resume evidence helper and wired it into `ResumePage`.
- Added a data-URI favicon to avoid dev-server 404 noise during browser smoke.

## Still open / blocked

- No GitHub issue, PR, or external release was created.
- More ambitious product slices are intentionally deferred: data quality review queue, richer export/template controls, and broader official-site adapter expansion.
- The current job workflow state is private/local only; no shared team/counselor workflow was added.
- Smoke testing wrote normal local data to `data/app.db`; this is runtime state, not a source artifact.

## Key files and artifacts

- `docs/plans/2026-06-18-product-remediation-execution.md`
- `docs/product/research-synthesis-2026-06-18.md`
- `docs/product/skills-and-workflow-map-2026-06-18.md`
- `backend/app/services/database.py`
- `backend/app/services/repositories.py`
- `backend/app/main.py`
- `backend/app/services/resume.py`
- `backend/tests/test_core_flow.py`
- `frontend/src/pages/Overview.tsx`
- `frontend/src/pages/JobsPage.tsx`
- `frontend/src/pages/ResumePage.tsx`
- `frontend/src/lib/workflow.ts`
- `frontend/src/lib/resumeEvidence.ts`
- `frontend/src/styles.css`

## Verification

- `uv run --project backend pytest -q` — passed: 93 tests, no warnings.
- `cd frontend; pnpm test` — passed: 4 files, 12 tests.
- `cd frontend; pnpm typecheck` — passed.
- `cd frontend; pnpm build` — passed.
- Browser smoke on `http://127.0.0.1:5173` — passed:
  - login,
  - overview double-entry onboarding,
  - fixture crawl,
  - example profile save,
  - resume generation,
  - evidence card rendering,
  - job detail/source evidence rendering.
- `GET http://127.0.0.1:8000/health` — returned `{"status":"ok"}`.

## Recommended next step

Run a focused `project-grill` on the next product slice: whether to prioritize a data-quality review queue, richer export controls, or job application workflow filters.

## Recommended reading order

1. `docs/plans/2026-06-18-product-remediation-execution.md`
2. `docs/handoffs/2026-06-18-product-remediation.md`
3. `backend/tests/test_core_flow.py`
4. `frontend/src/lib/workflow.ts`
5. `frontend/src/lib/resumeEvidence.ts`
6. `frontend/src/pages/Overview.tsx`
7. `frontend/src/pages/JobsPage.tsx`
8. `frontend/src/pages/ResumePage.tsx`

## Recommended skill / toolset

- `project-grill` for choosing the next product slice.
- `vertical-slice-planning` and `writing-plans` before broad UI/backend changes.
- `test-driven-development` for API, export, profile, and resume evidence changes.
- `systematic-debugging` for crawler, import/OCR, or migration issues.
- `requesting-code-review` before committing multi-file changes.
