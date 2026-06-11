# Tencent Cloud CVM Deployment Commands

These are the reusable commands from the successful 2026-06-10 deployment.

## Local Windows: Create Deployment Zip

Run from the project root on Windows PowerShell:

```powershell
cd "d:\开发\螃蟹的简历撰写工具"
$files = git ls-files
if (Test-Path medical-resume-tool-deploy.zip) { Remove-Item medical-resume-tool-deploy.zip }
tar -a -cf medical-resume-tool-deploy.zip @files
tar -tf medical-resume-tool-deploy.zip | Select-Object -First 40
```

The archive must preserve directory paths such as:

```text
backend/app/main.py
backend/app/services/exporter.py
frontend/src/App.tsx
frontend/package.json
```

Avoid using a packaging command that flattens directories.

## Local Windows: Upload Deployment Zip

```powershell
scp .\medical-resume-tool-deploy.zip ubuntu@110.42.136.106:/tmp/
```

## Server: Base Packages

```bash
sudo apt update
sudo apt install -y nginx git curl ca-certificates unzip fontconfig fonts-noto-cjk
```

Refresh/check fonts:

```bash
sudo fc-cache -fv
fc-match "Noto Sans CJK SC"
```

Expected output includes:

```text
NotoSansCJK-Regular.ttc: "Noto Sans CJK SC" "Regular"
```

## Server: Install Node 22

Ubuntu's default apt source installed Node 12, which was too old for this frontend. Use NodeSource Node 22.

Clean old packages if needed:

```bash
sudo apt remove -y libnode-dev libnode72 nodejs npm
sudo apt autoremove -y
sudo apt clean
```

Install Node 22:

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
node --version
npm --version
```

Expected:

```text
v22.x.x
```

If `dpkg` reports an overwrite conflict for `common.gypi`, use:

```bash
sudo dpkg -i --force-overwrite /var/cache/apt/archives/nodejs_*nodesource1_amd64.deb
sudo apt -f install -y
```

## Server: Install pnpm

```bash
sudo npm install -g pnpm
pnpm --version
```

If pnpm warns about ignored build scripts for `esbuild`, approve them:

```bash
cd /opt/medical-resume-tool/frontend
pnpm approve-builds
```

In the interactive prompt, approve `esbuild` entries.

## Server: Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
uv --version
```

If the shell cannot find `uv`, check:

```bash
/home/ubuntu/.local/bin/uv --version
command -v uv
```

## Server: Extract Code to /opt

Use `sudo` for writes under `/opt`.

```bash
cd /opt
sudo rm -rf /opt/medical-resume-tool
sudo mkdir -p /opt/medical-resume-tool
sudo unzip -o /tmp/medical-resume-tool-deploy.zip -d /opt/medical-resume-tool
sudo chown -R ubuntu:ubuntu /opt/medical-resume-tool
cd /opt/medical-resume-tool
```

Check structure:

```bash
ls
ls backend/app/services/exporter.py
ls frontend/src
```

Confirm Linux PDF font fix is present:

```bash
grep -n "CJK_FONT_CANDIDATES\|PDF_FONT_PATH\|helvetica" backend/app/services/exporter.py
```

Expected:

```text
CJK_FONT_CANDIDATES
PDF_FONT_PATH
```

There should be no old `pdf.set_font("helvetica", size=12)` fallback.

## Server: Backend Verification

```bash
cd /opt/medical-resume-tool
uv sync --project backend
uv run --project backend pytest -q
```

Expected:

```text
42 passed
```

## Server: Frontend Verification

```bash
cd /opt/medical-resume-tool/frontend
pnpm install
pnpm test
pnpm typecheck
pnpm build
```

Expected build output includes:

```text
dist/index.html
dist/assets/...
```

## Server: systemd Backend Service

```bash
cd /opt/medical-resume-tool
mkdir -p /opt/medical-resume-tool/backend/data
sudo chown -R ubuntu:ubuntu /opt/medical-resume-tool

UV_PATH="$(command -v uv)"

sudo tee /etc/systemd/system/medical-resume.service >/dev/null <<EOF
[Unit]
Description=Medical Resume Tool Backend
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/medical-resume-tool/backend
Environment="HOME=/home/ubuntu"
Environment="DATABASE_URL=sqlite:////opt/medical-resume-tool/backend/data/app.db"
ExecStart=${UV_PATH} run --project /opt/medical-resume-tool/backend uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable medical-resume
sudo systemctl restart medical-resume
sudo systemctl status medical-resume --no-pager
```

Expected:

```text
active (running)
```

Backend local health check:

```bash
curl http://127.0.0.1:8000/health
```

Expected:

```json
{"status":"ok"}
```

## Server: Nginx Config

```bash
sudo tee /etc/nginx/sites-available/medical-resume >/dev/null <<'EOF'
server {
    listen 80;
    server_name _;

    root /opt/medical-resume-tool/frontend/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/medical-resume /etc/nginx/sites-enabled/medical-resume
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

Expected:

```text
syntax is ok
test is successful
```

## Server: Smoke Checks

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1/health
curl http://127.0.0.1/api/jobs
```

Public checks:

```text
http://110.42.136.106/
http://110.42.136.106/health
http://110.42.136.106/api/jobs
```

## Server: Common Operations

Backend service:

```bash
sudo systemctl status medical-resume --no-pager
sudo systemctl restart medical-resume
journalctl -u medical-resume -n 100 --no-pager
```

Nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
sudo systemctl status nginx --no-pager
```

## Server: Manual SQLite Backup

```bash
sudo mkdir -p /opt/backups/medical-resume
sudo cp /opt/medical-resume-tool/backend/data/app.db "/opt/backups/medical-resume/app-$(date +%F-%H%M%S).db"
sudo ls -lh /opt/backups/medical-resume
```

Check database location:

```bash
ls -lh /opt/medical-resume-tool/backend/data
```

## Server: Update Deployment Later

1. Build a fresh `medical-resume-tool-deploy.zip` locally.
2. Upload it to `/tmp/`.
3. Preserve database before replacing code:

```bash
sudo mkdir -p /opt/backups/medical-resume
sudo cp /opt/medical-resume-tool/backend/data/app.db "/opt/backups/medical-resume/app-before-update-$(date +%F-%H%M%S).db"
```

4. Replace code:

```bash
cd /opt
sudo rm -rf /opt/medical-resume-tool-new
sudo mkdir -p /opt/medical-resume-tool-new
sudo unzip -o /tmp/medical-resume-tool-deploy.zip -d /opt/medical-resume-tool-new
sudo chown -R ubuntu:ubuntu /opt/medical-resume-tool-new
```

5. Copy database into the new deployment if needed, or keep `/opt/medical-resume-tool/backend/data/app.db` backed up before swapping directories.

For this MVP, the simpler replacement workflow used during initial deployment removed `/opt/medical-resume-tool`. That is fine before real data exists, but after real data is added it can delete SQLite data unless backed up first.

