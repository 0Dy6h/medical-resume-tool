# Agent Guide

## Project

This repo is a local MVP for Chinese medical job intelligence and truthful resume tailoring. It has a FastAPI/SQLite backend and a React/Vite frontend.

Read `CONTEXT.md` first for the domain vocabulary (trust levels A1, job identity A4, truthful-resume constraints, crawl singleflight). Those concepts each have one authoritative implementation location listed there — do not reinvent them elsewhere. Decision history lives in `docs/adr/`; runbook in `docs/runbook.md`; architecture overview in `docs/architecture.md`; end-user guide in `docs/user-guide.md`; dated execution plans in `docs/plans/`; deployment guide in `docs/deploy.md`; outdated top-level reports are parked in `docs/archive/`.

## Core Boundaries

- Do not generate resume facts that are absent from the structured profile.
- Keep every job record traceable to `source_url`, `source_text_hash`, `fetched_at`, and `parser_name`.
- Job identity is `(institution_id, source_url)` — never dedupe jobs by `source_text_hash` (identical-text announcements from different institutions must coexist), and archive the previous body to `job_snapshots` whenever a re-crawl sees changed content at the same identity (A4 溯源).
- Data trust levels (`real` / `placeholder` / `fixture` / `disabled`, implemented in `repositories.classify_job_trust`) drive the default jobs view. `placeholder` output (generic parser) must never masquerade as real data.
- MVP data collection is public official recruitment pages only. Do not add login-based platform scraping or anti-bot bypasses.
- The first six institutions use deterministic fixture data for demo stability. Six official-site adapters are enabled (`nfyy`, `z2hospital`, `bjmu`, `chinacdc`, `hrbmu`, `njmu`); disabled seeds have structured blocked reasons in `seeds.BLOCKED_REASONS`, exposed via the `/api/institutions` endpoint.
- PDF attachments are currently discovered and recorded as evidence only; do not add PDF table parsing unless the slice includes fixtures and tests.

## Commands

Backend:

```powershell
uv run --project backend pytest -q
cd backend; uv run --project . python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

> 注意：uvicorn 必须以 `python -m uvicorn` 且工作目录在 `backend/` 下启动
> （`app` 包位于 `backend/`）。直接从仓库根目录跑 `uv run --project backend uvicorn …`
> 会报 `ModuleNotFoundError: No module named 'app'`。
> 启动/停止方式（任选其一）：双击 `start.bat` / `stop.bat`（透传参数给
> `scripts/start-local.ps1`）；`pwsh -NoProfile -File scripts/start-local.ps1`
> （`-Stop` 停止，`-NoBrowser` 不自动开浏览器）；或全局命令 `tcmjob` / `tcmjob-stop`
> （任意目录可用，Ctrl+C/关窗由看门狗自动停全套服务，机制见 `scripts/README-tcmjob.md`）。
> 若要改动 `scripts/*.bat` 或 `D:\bin\tcmjob*.bat`：bat 必须保存为 **GBK 编码 + CRLF**，
> 等待用 `ping -n` 而非 `timeout`（本机 PATH 中 GNU coreutils 的 timeout 会抢占 Windows 版）。

> **SQLite path note:** the database path is relative to the current working directory. From the repo root it uses `data/app.db`; from `backend/` it uses `backend/data/app.db`. The two paths do not share data.

Frontend:

```powershell
cd frontend
pnpm test
pnpm typecheck
pnpm build
pnpm dev
```

## File Map

- `backend/app/main.py` - FastAPI routes and app factory.
- `backend/app/services/database.py` - SQLite schema and seed initialization.
- `backend/app/services/seeds.py` - 30 institution seed records.
- `backend/app/services/crawler.py` - fixture and generic crawler/parser, adapter dispatch.
- `backend/app/services/attachments.py` - attachment discovery, xlsx table parsing, and attachment-derived job construction.
- `backend/app/services/repositories.py` - data access layer plus data-trust classification (`classify_job_trust`).
- `backend/app/services/analytics.py` - analytics/report aggregation for the overview page; slices follow the trust classification (never counts `placeholder` as real).
- `backend/app/services/scheduler.py` - daily maintenance loop (auto-crawl then subscription scan) plus startup catch-up (`maybe_catch_up`: if no `trigger='auto'` crawl ran in the last 24h, one runs immediately at startup). The singleflight lock `try_acquire_crawl_slot` is defined in `crawler.py`; the scheduler only borrows it.
- `backend/app/services/http_client.py` - outbound fetch client: TLS enforced, private/loopback/cloud-metadata targets blocked, 10MB response cap.
- `backend/app/services/auth.py` - stdlib-only auth (scrypt passwords, self-signed HMAC session tokens; secret from `AUTH_SECRET` or persisted `data/.auth_secret`).
- `backend/app/services/adapters/nfyy.py` - 南方医院 announcement parser (real site adapter).
- `backend/app/services/adapters/z2hospital.py` - 浙大二院 listing+article parser.
- `backend/app/services/adapters/chinacdc.py` - 中疾控 listing+department notice parser.
- `backend/app/services/adapters/njmu.py` - 南京医科大学 listing+announcement parser.
- `backend/app/services/adapters/hrbmu.py` - 哈尔滨医科大学 listing+table parser.
- `backend/app/services/adapters/bjmu.py` - 北京大学医学部 listing+announcement parser.
- `backend/app/services/classifier.py` - rule-based category and tag extraction; still writes the persisted `jobs.requirements` column and job filters (do not change without a data migration).
- `backend/app/services/keyword_match.py` - subscription keyword semantics: non-ASCII keywords match by substring, pure-ASCII keywords match case-insensitively on word boundaries («ICU» must not hit «RICU»). `refine_keyword_hits` post-filters SQL LIKE results.
- `backend/app/services/profile_checks.py` - pure profile boundary checks (PRD 4.3): education/experience time-overlap detection (>50 % of the shorter range; unparseable dates never warn) and draft-reference counting by exact `profile_field_id`.
- `backend/app/services/profile_import/` - 履历资料导入 pipeline: docx/image text extraction (image OCR via pytesseract), fact extraction + normalization, and profile-contract construction (`pipeline.build_profile_contract`); legacy entry points are re-exported from the package `__init__`. Image OCR needs a local tesseract binary (`TESSERACT_CMD` env var); when absent it degrades gracefully — docx text still works, image text is skipped.
- `backend/app/services/matching/` - requirement segmentation (`segment.py`), CJK bigram tokenizer (`tokenize.py`), IDF-weighted semantic scorer (`scorer.py`), and the arithmetic degree gate (`gates.py`). `app/data/jd_idf.json` is the committed IDF table, rebuilt offline by `backend/scripts/build_idf.py`. Eligibility clauses (国籍/年龄/身体条件/遵纪守法 — `is_eligibility_clause` in `segment.py`) are excluded in the matching layer (`resume.py` skips them), NOT inside `segment.py`: mixed clauses containing degree words must stay visible to the degree gate, and both `test_jd_segmenter` and `test_matching_eval` pin this placement.
- `backend/app/services/resume.py` - profile-to-job matching (delegates to `matching/`) and truthful resume draft generation.
- `backend/app/services/exporter.py` - DOCX/PDF export.
- `backend/fixtures/nfyy/` - saved HTML fixtures for offline adapter testing.
- `backend/fixtures/z2hospital/` - 浙大二院 fixture HTML.
- `backend/fixtures/chinacdc/` - 中疾控 fixture HTML.
- `backend/fixtures/njmu/` - 南京医科大学 fixture HTML.
- `backend/fixtures/hrbmu/` - 哈尔滨医科大学 fixture HTML.
- `backend/fixtures/bjmu/` - 北京大学医学部 fixture HTML.
- `frontend/src/App.tsx` - frontend shell and navigation.
- `frontend/src/pages/` - workbench pages (tests live alongside as `*.test.ts`).
- `backend/scripts/` - offline utilities run from `backend/`: `build_idf.py` (IDF table), `export_preview.py`, `measure_jobs_layout.py`.
- `medical-job-prd/` - self-contained product PRD (static HTML, no build step).
- `docs/handoffs/` - session continuation notes.

## Verification Discipline

Run backend tests after backend changes. Run `pnpm test`, `pnpm typecheck`, and `pnpm build` after frontend changes. For cross-stack behavior, start both services and verify `/health`, `/api/jobs`, `/api/analytics/summary`, and `http://127.0.0.1:5173`.

> Gotcha: pnpm 的 run 前依赖检查曾在本机非交互终端误报并试图清空重建 node_modules
> （会把运行中的 Vite 一起干掉）。已在 `frontend/pnpm-workspace.yaml` 设
> `verifyDepsBeforeRun: false`，`pnpm test/typecheck/build` 可直接运行；
> 依赖变更后请显式执行 `pnpm install`。

When changing the requirement matcher (`backend/app/services/matching/`), keep `backend/tests/test_matching_eval.py` green — it enforces top-1 source accuracy, zero wrong-source attributions, and zero false positives over a tuning and a held-out profile. If you change `segment.py`, regenerate the IDF table with `python -m scripts.build_idf` (from `backend/`) so `app/data/jd_idf.json` stays reproducible.
