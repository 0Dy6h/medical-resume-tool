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

## Data

- Default database: `data/app.db` when launched from repo root.
- If launched from `backend/`, the relative default becomes `backend/data/app.db`.
- Override with `DATABASE_URL=sqlite:///absolute/or/relative/path.db` when a single fixed database location is needed.

## Known Operational Notes

- The Windows `python` command on this machine points to the Microsoft Store stub. Use `uv run --project backend ...` rather than `python ...`.
- SQLite connections use a closing connection factory because Windows keeps files locked if connections are not explicitly closed.
- Logs from the first implementation session were written to `logs/backend.log` and `logs/frontend.log` when services were started in hidden background processes.

