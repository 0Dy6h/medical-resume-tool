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

一键启动/停止（推荐）：

```powershell
pwsh -NoProfile -File scripts/start-local.ps1       # 启动：装依赖(非交互) + 起前后端 + 健康自检 + 开浏览器
pwsh -NoProfile -File scripts/start-local.ps1 -Stop # 停止（按 PID 文件 + 进程树，不误杀其他程序）
```

脚本把服务放在后台进程并写日志到 `logs/`（`backend.log` / `frontend.log`、PID 文件
`backend.pid` / `frontend.pid`）；关闭终端不会停止服务，需用 `-Stop` 停止。
若 8000/5173 端口被占用会明确报错并列出占用进程。脚本会对 pnpm 设 `CI=true`
并禁用交互确认，避免 node_modules 布局与 pnpm 版本不一致时永久卡在 “Proceed? (Y/n)”。

手动启动：

Backend (工作目录必须在 `backend/`，用 `python -m` 保证包可导入):

```powershell
cd backend
uv run --project . python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
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

## Daily Auto Crawl (U5)

- 调度器每天在 `SUBSCRIPTION_SCAN_HOUR:SUBSCRIPTION_SCAN_MINUTE`（默认 09:00）执行一次维护循环：
  先对全部已启用机构自动抓取（跑批记录 `trigger=auto`），随后扫描订阅推送。
- 用 `AUTO_CRAWL_ENABLED=false` 可单独关闭自动抓取（订阅扫描仍按原配置执行）。
- 抓取单飞：手动启动抓取时若已有任务在跑，接口返回 409「已有抓取任务在进行中」；
  自动抓取遇到占用会跳过本轮（日志留痕），订阅扫描不受影响。
- 自动抓取结果在「抓取任务」页的「最近任务」表中可见；机构级上次抓取时间与失败原因
  见同一页面的机构种子表（`last_crawled_at` / `last_status` / `last_error`）。

## Known Operational Notes

- The Windows `python` command on this machine points to the Microsoft Store stub. Use `uv run --project backend ...` rather than `python ...`.
- SQLite connections use a closing connection factory because Windows keeps files locked if connections are not explicitly closed.
- DOCX/PDF/TXT/Markdown import works with Python dependencies only. Image OCR and scanned-PDF OCR require the Tesseract executable on the host; set `TESSERACT_CMD` if it is not on `PATH`, and set `PROFILE_IMPORT_OCR_LANGUAGES` when using a non-default language pack.
- Logs from the first implementation session were written to `logs/backend.log` and `logs/frontend.log` when services were started in hidden background processes.
- On 2026-06-09, Vite dev-server smoke in this environment failed to bind `127.0.0.1:5173` and `127.0.0.1:5174` with `listen EACCES`; frontend `pnpm test`, `pnpm typecheck`, and `pnpm build` still passed. On 2026-06-10, the same local service smoke passed with backend `/health` on port 8000 and Vite on `http://127.0.0.1:5173`. If the bind error recurs, check Windows port reservations/security policy or try another allowed port.
