# Product Remediation Execution Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Turn the prepared readiness work into a verified MVP remediation pass focused on first-run guidance, job workflow state, evidence-centered resume review, and safe export defaults.

**Architecture:** Keep the existing FastAPI/SQLite backend and React/Vite workbench. Use the already-started job status, export-mode, workflow, and evidence helper changes as the baseline, then close gaps without broad rewrites.

**Tech Stack:** Python 3.11, FastAPI, SQLite, pytest, React, TypeScript, Vite, Vitest, pnpm.

---

## Product Decision

First-run onboarding uses two explicit entry paths:

- Stable demo path: load deterministic fixture institutions first so the job -> evidence -> resume aha moment is reliable.
- Private workflow path: import or edit local profile facts before generating truthful drafts.

This resolves the readiness-plan question without adding new account roles or public sharing.

## Slice 1: First-Run Guidance

**Objective:** Make the overview page explain the next action through two product paths and a three-step readiness checklist.

**Files:**

- Modify: `frontend/src/pages/Overview.tsx`
- Modify: `frontend/src/lib/workflow.ts`
- Test: `frontend/src/lib/workflow.test.ts`
- Modify: `frontend/src/styles.css`

**Steps:**

1. Keep existing workflow helper tests green.
2. Add helper behavior for stable-demo/private-workflow entry metadata if needed.
3. Render demo/private path actions in `Overview`.
4. Fix JSX text escaping and missing icon imports.
5. Run `pnpm test` and `pnpm typecheck`.

## Slice 2: Job Workflow State

**Objective:** Let a signed-in user save, triage, and annotate a job privately from job list/detail payloads.

**Files:**

- Modify: `backend/app/services/database.py`
- Modify: `backend/app/services/repositories.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/schemas.py`
- Test: `backend/tests/test_core_flow.py`
- Modify: `frontend/src/pages/JobsPage.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/types.ts`
- Test: `frontend/src/lib/status.test.ts`

**Steps:**

1. Preserve current backend tests for private status visibility.
2. Ensure unauthenticated job browsing still works.
3. Keep status labels and tones covered in frontend helper tests.
4. Run backend and frontend gates.

## Slice 3: Evidence-Centered Resume Review

**Objective:** Replace raw profile field display with readable requirement -> profile source -> evidence strength UI.

**Files:**

- Modify: `backend/app/services/resume.py`
- Test: `backend/tests/test_core_flow.py`
- Modify: `frontend/src/lib/resumeEvidence.ts`
- Test: `frontend/src/lib/resumeEvidence.test.ts`
- Modify: `frontend/src/pages/ResumePage.tsx`
- Modify: `frontend/src/styles.css`

**Steps:**

1. Keep backend evidence fields covered: `source_label`, `matched_terms`, and `evidence_strength`.
2. Use frontend evidence helpers in the resume evidence panel.
3. Ensure gaps remain separate from editable/exportable application content.
4. Run `pnpm test`, `pnpm typecheck`, and backend tests.

## Slice 4: Employer Export Safety

**Objective:** Export application copies without internal gap diagnostics by default, while keeping an explicit diagnostic mode.

**Files:**

- Modify: `backend/app/main.py`
- Test: `backend/tests/test_core_flow.py`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/pages/ResumePage.tsx`

**Steps:**

1. Preserve backend test proving application export excludes the gaps section.
2. Add explicit diagnostic export affordance only if it does not confuse the main employer-facing action.
3. Run backend export tests and full frontend build.

## Verification

Run before completion:

```powershell
uv run --project backend pytest -q
cd frontend
pnpm test
pnpm typecheck
pnpm build
```

For UI changes, start the app and inspect the main workbench pages with Playwright if the build is green.
