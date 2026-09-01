# Agent Guide

## Project

This repo is a local MVP for Chinese medical job intelligence and truthful resume tailoring. It has a FastAPI/SQLite backend and a React/Vite frontend.

## Core Boundaries

- Do not generate resume facts that are absent from the structured profile.
- Keep every job record traceable to `source_url`, `source_text_hash`, `fetched_at`, and `parser_name`.
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
> 一键启动/停止（含日志与健康自检）：`pwsh -NoProfile -File scripts/start-local.ps1`
> （`-Stop` 停止，`-NoBrowser` 不自动开浏览器）。

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
- `backend/app/services/adapters/nfyy.py` - 南方医院 announcement parser (real site adapter).
- `backend/app/services/adapters/z2hospital.py` - 浙大二院 listing+article parser.
- `backend/app/services/adapters/chinacdc.py` - 中疾控 listing+department notice parser.
- `backend/app/services/adapters/njmu.py` - 南京医科大学 listing+announcement parser.
- `backend/app/services/adapters/hrbmu.py` - 哈尔滨医科大学 listing+table parser.
- `backend/app/services/adapters/bjmu.py` - 北京大学医学部 listing+announcement parser.
- `backend/app/services/classifier.py` - rule-based category and tag extraction; still writes the persisted `jobs.requirements` column and job filters (do not change without a data migration).
- `backend/app/services/matching/` - requirement segmentation (`segment.py`), CJK bigram tokenizer (`tokenize.py`), IDF-weighted semantic scorer (`scorer.py`), and the arithmetic degree gate (`gates.py`). `app/data/jd_idf.json` is the committed IDF table, rebuilt offline by `backend/scripts/build_idf.py`.
- `backend/app/services/resume.py` - profile-to-job matching (delegates to `matching/`) and truthful resume draft generation.
- `backend/app/services/exporter.py` - DOCX/PDF export.
- `backend/fixtures/nfyy/` - saved HTML fixtures for offline adapter testing.
- `backend/fixtures/z2hospital/` - 浙大二院 fixture HTML.
- `backend/fixtures/chinacdc/` - 中疾控 fixture HTML.
- `backend/fixtures/njmu/` - 南京医科大学 fixture HTML.
- `backend/fixtures/hrbmu/` - 哈尔滨医科大学 fixture HTML.
- `backend/fixtures/bjmu/` - 北京大学医学部 fixture HTML.
- `frontend/src/App.tsx` - frontend shell and navigation.
- `frontend/src/pages/` - workbench pages.
- `docs/handoffs/` - session continuation notes.

## Verification Discipline

Run backend tests after backend changes. Run `pnpm test`, `pnpm typecheck`, and `pnpm build` after frontend changes. For cross-stack behavior, start both services and verify `/health`, `/api/jobs`, `/api/analytics/summary`, and `http://127.0.0.1:5173`.

When changing the requirement matcher (`backend/app/services/matching/`), keep `backend/tests/test_matching_eval.py` green — it enforces top-1 source accuracy, zero wrong-source attributions, and zero false positives over a tuning and a held-out profile. If you change `segment.py`, regenerate the IDF table with `python -m scripts.build_idf` (from `backend/`) so `app/data/jd_idf.json` stays reproducible.
