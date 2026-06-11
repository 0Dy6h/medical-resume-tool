# Tencent Cloud CVM Deployment Record - 2026-06-10

## Goal

Deploy the Chinese medical job intelligence and truthful resume tailoring MVP to a Tencent Cloud server so it can be accessed over the public internet.

## Final Result

Deployment succeeded.

- Public URL: `http://110.42.136.106/`
- Health check: `http://110.42.136.106/health`
- API example: `http://110.42.136.106/api/jobs`
- Backend test result on server: `42 passed, 1 warning`
- Frontend verification on server:
  - `pnpm test` passed, `5 passed`
  - `pnpm typecheck` passed
  - `pnpm build` passed
- Website opened successfully in browser.

## Server

- Provider: Tencent Cloud
- Product: CVM free trial
- Instance shape: Standard S5, 2 vCPU, 2 GB RAM
- Bandwidth: 3 Mbps
- System disk: 50 GB SSD
- Region: Shanghai
- OS: Ubuntu Server 22.04 LTS 64-bit
- Login user used during deployment: `ubuntu`
- Public IP at deployment time: `110.42.136.106`

This was selected as a one-month validation environment. It is suitable for demo and deployment verification, but not yet a hardened production environment.

## Runtime Architecture

```text
Browser
  -> http://110.42.136.106
  -> Nginx on port 80
  -> frontend/dist static assets
  -> /api and /health reverse proxy
  -> FastAPI on 127.0.0.1:8000
  -> SQLite database at backend/data/app.db
```

Only ports `22`, `80`, and optionally `443` should be opened in Tencent Cloud security groups. Do not expose `8000` or `5173` publicly.

## Important Deployment Decisions

- Use one CVM instance only for the MVP.
- Do not add RDS yet. SQLite is enough for this stage.
- Serve the frontend as static production assets from Nginx.
- Run FastAPI behind Nginx on `127.0.0.1:8000`.
- Use `systemd` to keep the backend alive and restart it after reboot.
- Install `fonts-noto-cjk` so PDF export supports Chinese text on Ubuntu.
- Upload a local deployment zip instead of cloning with GitHub password authentication.

## Repository Change Made During Deployment

Linux PDF export initially failed because `backend/app/services/exporter.py` only looked for the Windows Microsoft YaHei font and then fell back to Helvetica, which cannot encode Chinese text.

The file was changed to search common CJK font paths on Linux, macOS, and Windows, and to support `PDF_FONT_PATH` as an override.

Relevant file:

- `backend/app/services/exporter.py`

Local verification after the change:

```powershell
uv run --project backend pytest -q
```

Result:

```text
42 passed, 1 warning
```

This fix should be committed and pushed before future GitHub-based deployments:

```powershell
git add backend/app/services/exporter.py
git commit -m "fix: support CJK fonts for PDF export on Linux"
git push
```

## Server Paths

- App root: `/opt/medical-resume-tool`
- Backend: `/opt/medical-resume-tool/backend`
- Frontend build output: `/opt/medical-resume-tool/frontend/dist`
- SQLite database: `/opt/medical-resume-tool/backend/data/app.db`
- systemd unit: `/etc/systemd/system/medical-resume.service`
- Nginx site config: `/etc/nginx/sites-available/medical-resume`
- Enabled Nginx site: `/etc/nginx/sites-enabled/medical-resume`
- Suggested local-server backup directory: `/opt/backups/medical-resume`

## Security Group

Minimum inbound rules:

```text
TCP 22   source: your current public IP /32 if possible; temporary 0.0.0.0/0 during setup only
TCP 80   source: 0.0.0.0/0
TCP 443  source: 0.0.0.0/0, reserved for future HTTPS
```

Do not open:

```text
8000
5173
3000
3306
6379
```

Outbound can remain open for package installation, crawler access to public recruitment pages, GitHub, npm, and Python package downloads.

## Verification Performed

Backend:

```bash
cd /opt/medical-resume-tool
uv run --project backend pytest -q
```

Result:

```text
42 passed, 1 warning
```

Frontend:

```bash
cd /opt/medical-resume-tool/frontend
pnpm test
pnpm typecheck
pnpm build
```

Result:

```text
2 frontend test files passed
5 frontend tests passed
typecheck passed
vite production build passed
```

Service and public checks:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1/health
curl http://127.0.0.1/api/jobs
```

Browser check:

```text
http://110.42.136.106/
```

Result: website opened successfully.

## Operational Notes

- The app is currently HTTP-only. Browsers may mark it as not secure.
- Do not enter sensitive real resume data unless access control and HTTPS are added.
- If the free trial expires and the instance is not renewed, the site will stop.
- If the instance is released or reinstalled, local SQLite data will be lost unless backed up.
- If the public IP changes, the access URL changes too.
- Since the database is local SQLite, backup discipline matters.

## Immediate Follow-ups

1. Restrict SSH security group source from `0.0.0.0/0` to the user's public IP `/32`.
2. Commit and push the Linux CJK PDF export fix.
3. Add a scheduled SQLite backup.
4. Add a domain and HTTPS before sharing with real users.
5. Add authentication or access control before collecting real personal resume data.
6. Consider moving from the one-month CVM trial to a yearly low-cost Tencent Cloud Lighthouse instance after validation.

