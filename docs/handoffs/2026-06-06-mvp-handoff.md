# Medical Job Intelligence MVP Handoff

## Goal

Build a local MVP for Chinese medical job intelligence and truthful resume tailoring. The current stage is a runnable end-to-end implementation with backend APIs, frontend workbench, fixture-backed crawl demo, analytics, structured profile storage, resume draft generation, and DOCX/PDF export.

## Current state

- The repo now contains a FastAPI/SQLite backend and React/Vite frontend.
- `README.md`, `AGENTS.md`, `docs/architecture.md`, and `docs/runbook.md` describe setup, architecture, and operating boundaries.
- The first six institution seeds use deterministic fixture jobs; the full seed list has 30 institutions.
- Backend and frontend checks passed during this session.
- Background dev servers were started for verification and should be stopped at session close if still running.

## Completed in this session

- Created backend schema, seed initialization, repositories, crawl run API, fixture/generic crawler, classifier, analytics, reports, profile storage, resume matching, and export endpoints.
- Created frontend workbench pages: overview, crawl tasks, job library, analytics/report, structured profile, and resume generation.
- Added tests covering core backend flows and a small frontend helper test.
- Added setup docs, project boundaries, architecture notes, and this handoff.

## Still open / blocked

- Real official-site adapters are not yet implemented for the 24 disabled generic seeds.
- Third-party recruitment platforms remain intentionally out of scope.
- OpenAI-compatible LLM configuration is reserved in `.env.example`, but the MVP currently uses deterministic rule-based extraction and generation.
- PDF export is intentionally simple; DOCX is the better editable output for first use.
- No git repository was initialized in this workspace during this session.

## Key files and artifacts

- `README.md`
- `.env.example`
- `AGENTS.md`
- `backend/app/main.py`
- `backend/app/services/database.py`
- `backend/app/services/seeds.py`
- `backend/app/services/crawler.py`
- `backend/app/services/classifier.py`
- `backend/app/services/resume.py`
- `backend/app/services/exporter.py`
- `backend/tests/test_core_flow.py`
- `frontend/src/App.tsx`
- `frontend/src/pages/`
- `docs/architecture.md`
- `docs/runbook.md`

## Verification

- `uv run --project backend pytest -q` - passed, 5 tests.
- `pnpm test` from `frontend/` - passed, 2 tests.
- `pnpm typecheck` from `frontend/` - passed.
- `pnpm build` from `frontend/` - passed.
- `GET http://127.0.0.1:8000/health` - returned `ok`.
- `POST /api/crawl-runs` with seeds `[1,2,3,4,5,6]` - completed with 10 jobs and 0 failures.
- `GET http://127.0.0.1:5173` - returned HTTP 200.

## Recommended next step

Implement the next vertical slice: add one real official hospital adapter with saved HTML fixtures, parser tests, live crawl error handling, and data-quality review fields. Keep the fixture path so demos remain stable.

## Recommended reading order

1. `README.md`
2. `AGENTS.md`
3. `docs/architecture.md`
4. `docs/runbook.md`
5. `backend/tests/test_core_flow.py`
6. `backend/app/services/crawler.py`
7. `frontend/src/pages/CrawlPage.tsx`

## Recommended skill / toolset

- `test-driven-development` for each adapter or API slice.
- `systematic-debugging` for live-site parser failures.
- `frontend-design` for UI changes.
- `terminal` and `file` tools for verification and edits.
