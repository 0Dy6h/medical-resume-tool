# Attachment-Aware Data Loop Handoff — 2026-06-09

## Goal

Upgrade the real official-site recruitment adapters into an attachment-aware data-quality loop. The project now parses public xlsx job tables from official announcement attachments where feasible, keeps attachment-level evidence in existing job metadata, and exposes source/attachment evidence in the frontend workbench.

## Current state

- The repo is a git worktree with uncommitted changes from this session and earlier same-day work. Do not assume a clean tree.
- 30 institution seeds exist. 12 are currently enabled: 6 deterministic fixture institutions plus 6 real official-site adapters: `nfyy`, `z2hospital`, `bjmu`, `chinacdc`, `hrbmu`, and `njmu`.
- `bjmu` and `chinacdc` can parse downloaded `.xlsx/.xls` attachments into row-level `ParsedJob` records.
- `njmu` and `hrbmu` record discovered attachment metadata, but PDF table parsing remains intentionally deferred.
- Job traceability remains on existing fields: `source_url`, `source_text_hash`, `fetched_at`, `parser_name`, plus attachment details inside `extraction_evidence`.
- The frontend job detail page now shows source evidence and attachment evidence. The crawl page shows partial/failure details.

## Completed in this session

- Added `backend/app/services/attachments.py` for:
  - official-page attachment link discovery for `.xlsx`, `.xls`, and `.pdf`;
  - deterministic `openpyxl` xlsx row parsing;
  - row-level `ParsedJob` creation with attachment evidence.
- Added `openpyxl` to backend dependencies and refreshed `backend/uv.lock`.
- Upgraded `backend/app/services/adapters/bjmu.py` and `backend/app/services/adapters/chinacdc.py`:
  - keep announcement-level records;
  - parse xlsx attachments into row-level jobs;
  - mark download/parse failures in `extraction_evidence.attachments` instead of failing the whole article.
- Added attachment metadata discovery to `backend/app/services/adapters/njmu.py` and `backend/app/services/adapters/hrbmu.py`.
- Stabilized same-day uncommitted improvements:
  - semantic HTML report rendering;
  - Chinese-capable PDF export via `fpdf2`;
  - extended profile fields: publications, teaching, awards;
  - `httpx.TransportError` retry coverage.
- Frontend updates:
  - `partial` status now displays as `部分完成`;
  - crawl run failures are visible on the crawl page;
  - job detail shows source URL/hash, parser, confidence, announcement URL, attachment URL, sheet, and row where available.

## Still open / blocked

- Changes are not committed. Next session should review and commit or split into commits.
- Frontend live dev-server smoke could not bind local ports in this Windows environment: Vite returned `listen EACCES` on both `127.0.0.1:5173` and `127.0.0.1:5174`. `pnpm test`, `pnpm typecheck`, and `pnpm build` all passed.
- PDF parsing is not implemented. PDF attachments are discovered and recorded only.
- Live adapter crawling works in the backend API smoke, but public websites can change; keep fixture-backed tests as the reliable contract.
- Remaining disabled seeds still need source-specific reconnaissance/adapters or explicit blocked reasons.

## Key files and artifacts

- `backend/app/services/attachments.py`
- `backend/app/services/adapters/bjmu.py`
- `backend/app/services/adapters/chinacdc.py`
- `backend/app/services/adapters/njmu.py`
- `backend/app/services/adapters/hrbmu.py`
- `backend/tests/test_attachments.py`
- `backend/tests/test_adapters.py`
- `backend/tests/test_core_flow.py`
- `frontend/src/pages/JobsPage.tsx`
- `frontend/src/pages/CrawlPage.tsx`
- `frontend/src/lib/status.ts`
- `frontend/src/lib/status.test.ts`
- Prior handoffs:
  - `docs/handoffs/2026-06-09-adapter-batch1.md`
  - `docs/handoffs/2026-06-09-real-adapter.md`

## Verification

- `uv run --project backend pytest -q` — passed: 39 tests, 1 existing Starlette/httpx deprecation warning.
- `cd frontend; pnpm test` — passed: 4 tests.
- `cd frontend; pnpm typecheck` — passed.
- `cd frontend; pnpm build` — passed.
- Backend API smoke with a temp SQLite database:
  - `/health` returned `ok`;
  - crawl `[1,2,3,4,5,6,11,19,21,27,28,7]` returned `completed`;
  - `success_count: 271`, `failure_count: 0`;
  - `/api/jobs` returned 174 deduped jobs;
  - `/api/analytics/summary` reported 174 jobs.
- Confirmed no lingering listeners on ports 8000 or 5173 after smoke attempts.

## Recommended next step

Review the dirty worktree, then create a commit boundary. A good split is:

1. Backend attachment parsing and adapter tests.
2. Frontend source-evidence UI.
3. Documentation/handoff updates.

After that, pick the next vertical slice: add one more source-specific adapter from the Tier 2 candidates or add a small adapter quality-review workflow for sampled parsed jobs.

## Recommended reading order

1. `docs/handoffs/2026-06-09-attachment-aware-data-loop.md`
2. `git status --short` and `git diff --stat`
3. `backend/app/services/attachments.py`
4. `backend/tests/test_attachments.py`
5. `backend/tests/test_adapters.py`
6. `frontend/src/pages/JobsPage.tsx`
7. `docs/handoffs/2026-06-09-adapter-batch1.md`

## Recommended skill / toolset

- `test-driven-development` for the next adapter or parsing slice.
- `systematic-debugging` if a live official site changes structure.
- `frontend-design` only for user-facing UI changes.
- Standard checks: `uv run --project backend pytest -q`, `pnpm test`, `pnpm typecheck`, `pnpm build`.
