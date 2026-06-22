# Runbook

## Install

Backend dependencies are managed by `uv` from `backend/pyproject.toml`. Frontend dependencies are managed by `pnpm` from `frontend/package.json`.

```powershell
uv run --project backend pytest -q
cd frontend
pnpm install
pnpm test
pnpm typecheck
pnpm build
```

## Start Services

Backend:

```powershell
uv run --project backend uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd frontend
pnpm dev
```

URLs:

- Frontend: `http://127.0.0.1:5173`
- Backend: `http://127.0.0.1:8000`
- Health: `http://127.0.0.1:8000/health`

## Smoke Test

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod -Method Post -ContentType 'application/json' -Body '{"institution_ids":[1,2,3,4,5,6]}' http://127.0.0.1:8000/api/crawl-runs
Invoke-RestMethod http://127.0.0.1:8000/api/jobs
Invoke-RestMethod http://127.0.0.1:8000/api/analytics/summary
```

Expected MVP demo result after crawling seeds 1-6: 10 fixture jobs, 6 institutions, and non-empty analytics.

To smoke-test the enabled real adapters as well:

```powershell
Invoke-RestMethod -Method Post -ContentType 'application/json' -Body '{"institution_ids":[1,2,3,4,5,6,11,19,21,27,28,7]}' http://127.0.0.1:8000/api/crawl-runs
Invoke-RestMethod http://127.0.0.1:8000/api/jobs
Invoke-RestMethod http://127.0.0.1:8000/api/analytics/summary
```

Public sites can change or rate-limit, so fixture tests remain the stable contract. A 2026-06-09 backend API smoke with a temp SQLite database completed this 12-institution crawl with 174 deduped jobs.

## Data

- Default database: `data/app.db` when launched from repo root.
- If launched from `backend/`, the relative default becomes `backend/data/app.db`.
- Override with `DATABASE_URL=sqlite:///absolute/or/relative/path.db` when a single fixed database location is needed.

## Known Operational Notes

- The Windows `python` command on this machine points to the Microsoft Store stub. Use `uv run --project backend ...` rather than `python ...`.
- SQLite connections use a closing connection factory because Windows keeps files locked if connections are not explicitly closed.
- DOCX/PDF/TXT/Markdown import works with Python dependencies only. Image OCR and scanned-PDF OCR require the Tesseract executable on the host; set `TESSERACT_CMD` if it is not on `PATH`, and set `PROFILE_IMPORT_OCR_LANGUAGES` when using a non-default language pack.
- Logs from the first implementation session were written to `logs/backend.log` and `logs/frontend.log` when services were started in hidden background processes.
- On 2026-06-09, Vite dev-server smoke in this environment failed to bind `127.0.0.1:5173` and `127.0.0.1:5174` with `listen EACCES`; frontend `pnpm test`, `pnpm typecheck`, and `pnpm build` still passed. On 2026-06-10, the same local service smoke passed with backend `/health` on port 8000 and Vite on `http://127.0.0.1:5173`. If the bind error recurs, check Windows port reservations/security policy or try another allowed port.
