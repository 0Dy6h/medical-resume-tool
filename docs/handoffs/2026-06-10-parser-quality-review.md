# Parser Quality Review Handoff — 2026-06-10

## Goal

Close the 2026-06-10 development plan: verify and commit the attachment-aware data loop, add a small parser-quality review slice, run backend/frontend/API/local-service smoke checks, and leave a clean continuation note.

## Current state

- The first 12 institutions are enabled: 6 deterministic fixture institutions plus 6 official-site adapters: `nfyy`, `z2hospital`, `bjmu`, `chinacdc`, `hrbmu`, and `njmu`.
- Official-site attachment handling is in place:
  - `bjmu` and `chinacdc` parse `.xlsx/.xls` public attachments into row-level jobs.
  - `njmu` and `hrbmu` record discovered attachment metadata.
  - PDF attachments remain discovery/evidence only; no PDF table parsing has been added.
- `/api/analytics/summary` now returns `parser_quality`, grouped by `parser_name`.
- The frontend analysis page now shows a compact parser-quality table with jobs, attachment rows, low-confidence count, failed attachment events, average confidence, and review status.
- `.vscode/` is ignored because the only local file present was a personal editor font-size setting.

## Commits created

1. `4233f97 feat: parse official recruitment attachments`
2. `40fd4ec feat: add backend quality and export safeguards`
3. `6f38950 feat: show source and parser quality evidence`
4. This handoff plus README/runbook/architecture updates are part of the final documentation commit.

## Verification

- `uv run --project backend pytest -q` — passed: 40 tests, 1 existing Starlette/httpx deprecation warning.
- `cd frontend; pnpm test` — passed: 5 tests.
- `cd frontend; pnpm typecheck` — passed.
- `cd frontend; pnpm build` — passed.
- Backend API smoke with a temp SQLite database:
  - `/health` returned `200 {"status":"ok"}`;
  - crawled `[1,2,3,4,5,6,11,19,21,27,28,7]`;
  - crawl returned `completed`, `success_count: 271`, `failure_count: 0`;
  - `/api/jobs` returned 174 deduped jobs;
  - `/api/analytics/summary` totals: `jobs: 174`, `institutions: 12`, `regions: 7`, `parsers: 11`, `low_confidence_jobs: 0`, `attachment_sourced_jobs: 113`, `failed_attachment_events: 0`.
- Local service smoke:
  - backend `http://127.0.0.1:8000/health` returned `ok`;
  - frontend `http://127.0.0.1:5173` returned status 200;
  - no lingering listeners remained on ports 8000 or 5173 after the smoke.

## Notable parser-quality output

- `chinacdc-xlsx-v1`: 92 jobs, average confidence 0.95, `stable`.
- `bjmu-xlsx-v1`: 21 jobs, average confidence 0.92, `stable`.
- `hrbmu-table-v1`: 2 jobs, average confidence 0.70, `watch`.

`hrbmu-table-v1` is the first good manual-review target because it is not failing, but its confidence is below the 0.80 watch threshold.

## Still open

- Remaining disabled seeds still need source-specific reconnaissance/adapters or explicit blocked reasons.
- Public official pages can change; fixture-backed tests remain the reliable contract.
- PDF parsing is intentionally deferred until a slice includes fixtures, parser choice, and tests.
- Parser-quality status is heuristic:
  - `review` if a parser has failed attachment events or low-confidence jobs below 0.65;
  - `watch` if average confidence is below 0.80;
  - otherwise `stable`.

## Recommended next step

Add a tiny review workflow for sampled parser output before adding another source adapter:

1. Start with `hrbmu-table-v1`.
2. Add a backend sample endpoint or analytics drilldown that returns 3-5 representative jobs for a parser.
3. Show the sampled source/evidence rows in the frontend analysis page or job list filter.
4. Keep this read-only; do not introduce manual labels or mutation until the review surface proves useful.
