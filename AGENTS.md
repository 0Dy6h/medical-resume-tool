# Agent Guide

## Project

This repo is a local MVP for Chinese medical job intelligence and truthful resume tailoring. It has a FastAPI/SQLite backend and a React/Vite frontend.

## Core Boundaries

- Do not generate resume facts that are absent from the structured profile.
- Keep every job record traceable to `source_url`, `source_text_hash`, `fetched_at`, and `parser_name`.
- MVP data collection is public official recruitment pages only. Do not add login-based platform scraping or anti-bot bypasses.
- The first six institutions use deterministic fixture data for demo stability; the remaining seed institutions are disabled generic crawlers until source-specific adapters are added.

## Commands

Backend:

```powershell
uv run --project backend pytest -q
uv run --project backend uvicorn app.main:app --host 127.0.0.1 --port 8000
```

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
- `backend/app/services/adapters/nfyy.py` - 南方医院 announcement parser (real site adapter).
- `backend/app/services/adapters/z2hospital.py` - 浙大二院 listing+article parser.
- `backend/app/services/adapters/chinacdc.py` - 中疾控 listing+department notice parser.
- `backend/app/services/adapters/njmu.py` - 南京医科大学 listing+announcement parser.
- `backend/app/services/adapters/hrbmu.py` - 哈尔滨医科大学 listing+table parser.
- `backend/app/services/adapters/bjmu.py` - 北京大学医学部 listing+announcement parser.
- `backend/app/services/classifier.py` - rule-based category and tag extraction.
- `backend/app/services/resume.py` - profile-to-job matching and truthful resume draft generation.
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

