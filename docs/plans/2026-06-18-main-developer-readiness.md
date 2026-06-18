# Main Developer Readiness Plan

> **For Hermes:** Use `project-grill` before implementing any product changes from this plan. Use `vertical-slice-planning` and `writing-plans` for each accepted slice.

**Goal:** Prepare the repository and next developer for product-focused execution without starting product remediation in this session.

**Architecture:** The current application remains FastAPI/SQLite plus React/Vite. Future changes should preserve official-source traceability, truth-constrained resume generation, fixture-backed tests, and local-first privacy.

**Tech Stack:** Python 3.11+, FastAPI, SQLite, pytest, React, TypeScript, Vite, Vitest, pnpm, uv, Tesseract OCR.

---

## Current Verified Baseline

- Backend dependency sync: `uv sync --project backend --all-groups` passed.
- Frontend dependency sync: `pnpm install --frozen-lockfile` passed.
- Backend tests: `uv run --project backend pytest -q` -> 86 passed, 1 Starlette/httpx deprecation warning at readiness time. Follow-up remediation resolved this warning with backend dev dependency `httpx2`.
- Frontend tests: `pnpm test` -> 5 passed.
- Frontend typecheck: `pnpm typecheck` passed.
- Frontend build: `pnpm build` passed.
- Tesseract executable found at `C:\Program Files\Tesseract-OCR\tesseract.exe`.
- Tesseract language packs include `chi_sim`, `chi_tra`, and `eng`.
- CodeGraph is indexed and usable for symbol navigation.

## Dependency Notes

- Canonical backend dependency source: `backend/pyproject.toml`.
- `backend/requirements.txt` has been aligned with PDF/image/OCR import dependencies for compatibility with requirements-based deployment.
- Frontend package install is healthy, but pnpm reported ignored build scripts for `esbuild`; current test/typecheck/build still passed.
- Use `uv run --project backend ...` rather than system `python`.

## Recommended Product Execution Order

### Slice 1: First-Run Guidance

Type: HITL before implementation, then AFK.

Goal:

- Make the first screen tell users exactly how to reach the job -> evidence -> resume aha moment.

Why first:

- It reduces demo friction without changing core backend behavior.
- It exposes whether the current workflow is understandable.

Acceptance criteria draft:

- Empty data state offers stable demo crawl.
- Empty profile state offers import, manual fill, or example profile.
- Resume generation page explains prerequisite state through actions, not docs.
- Existing backend/frontend tests still pass.

Verification:

- `uv run --project backend pytest -q`
- `cd frontend; pnpm test; pnpm typecheck; pnpm build`
- Browser smoke: register/login -> load demo data -> load example profile -> generate draft.

### Slice 2: Evidence-Centered Resume Generation UX

Type: HITL before implementation, then AFK.

Goal:

- Replace raw `profile_field_id` presentation with human-readable requirement -> evidence -> draft mapping.

Why second:

- This is the product's differentiator.

Acceptance criteria draft:

- Evidence cards show requirement, matched profile collection/title, source text, and matched terms.
- Gaps are separate from exportable resume content.
- No generated statement can lack a profile source or explicit supporting level.

Verification:

- Add/extend backend tests around evidence shape only if API contract changes.
- Add/extend frontend tests for evidence formatting helpers.
- Full backend/frontend gates.

### Slice 3: Employer-Facing Export vs Diagnostic Draft

Type: HITL.

Goal:

- Prevent internal gap diagnostics from accidentally appearing in employer-facing exports.

Decision needed:

- Should gaps be excluded by default from all exports, or should the user choose "diagnostic" vs "application" export?

Verification:

- Backend export tests prove chosen behavior.
- Manual export smoke for DOCX and PDF.

### Slice 4: Job Workflow State

Type: HITL.

Goal:

- Let users save, triage, and track jobs as actionable applications.

Minimal behavior:

- Save/unsave job.
- Status: evaluating, preparing, applied, archived.
- Optional note and deadline display.

Verification:

- Backend API tests for user-scoped job state.
- Frontend helper tests.
- Manual flow: save job -> status persists -> filter or display status.

### Slice 5: Data Quality Review Queue

Type: AFK after scope accepted.

Goal:

- Turn parser quality metrics into actionable review items.

Minimal behavior:

- Show low-confidence jobs and failed attachment events in a queue.
- Allow marking as reviewed or ignored locally.

Verification:

- Fixture-backed parser-quality tests.
- Frontend build/typecheck.

## Open Product Decisions

1. Should the next UX prioritize individual job seekers only, or also keep future counselor/employment-office workflows open?
2. Should exported resumes ever include gap diagnostics?
3. Is "match score" acceptable, or should the product use only evidence counts and strength labels to avoid false precision?
4. Should job workflow state be local-user private, or shared/public across users?
5. How much data-quality tooling should normal users see versus an advanced/admin view?

## Non-Negotiable Guardrails

- Do not generate resume facts absent from structured profile data.
- Keep every job traceable to source URL, hash, fetch time, and parser.
- Do not add login-based platform scraping or anti-bot bypasses.
- Keep fixture-backed deterministic tests for crawler/parser changes.
- Do not parse PDF tables unless the slice includes fixtures and tests.
- Do not let market analytics imply full-market coverage.

## Recommended Reading Order For Main Developer

1. `README.md` - product shape and use order.
2. `AGENTS.md` - repo-specific constraints.
3. `docs/architecture.md` - data flow and API surface.
4. `docs/product/research-synthesis-2026-06-18.md` - external lessons and positioning.
5. `docs/product/skills-and-workflow-map-2026-06-18.md` - execution workflow.
6. `frontend/src/pages/ResumePage.tsx` and `backend/app/services/resume.py` - current evidence workflow.
7. `backend/tests/test_core_flow.py` - end-to-end backend behavior contracts.

## Recommended Next Action

Run `project-grill` on Slice 1 and ask exactly one product question first:

> Should first-run onboarding optimize for a stable demo experience, a real-user private workflow, or both with separate buttons?

Once answered, create a detailed implementation plan under `docs/plans/` and implement with TDD.
