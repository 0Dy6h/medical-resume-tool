# Tencent Cloud CVM Deployment Troubleshooting Notes

These are the issues encountered during the 2026-06-10 Tencent Cloud CVM deployment and how they were resolved.

## SSH Login Failed for root

Symptom:

```text
root@110.42.136.106's password:
Permission denied, please try again.
```

Cause:

Ubuntu cloud images often do not allow direct root password login, or the root password differs from the instance login user.

Resolution:

Use the Ubuntu default user:

```powershell
ssh ubuntu@110.42.136.106
```

If needed, reset the instance password from the Tencent Cloud console and log in as `ubuntu`.

## Ubuntu apt Prompt: Daemons Using Outdated Libraries

Symptom:

A purple package configuration dialog appears:

```text
Daemons using outdated libraries
Which services should be restarted?
```

Resolution:

Keep the defaults, press `Tab` to select `<Ok>`, then press `Enter`.

This is normal after package upgrades. If SSH disconnects, reconnect.

## npm Global Install Permission Denied

Symptom:

```text
npm ERR! EACCES: permission denied, mkdir '/usr/local/lib/node_modules'
```

Cause:

The `ubuntu` user cannot write global npm directories without elevated privileges.

Resolution:

Use:

```bash
sudo npm install -g pnpm
```

## Node 12 Was Too Old

Symptom:

```text
npm WARN EBADENGINE Unsupported engine
required: { node: '>=22.13' }
current: { node: 'v12.22.9' }
```

Cause:

Ubuntu apt installed Node 12 from the default distribution repository.

Resolution:

Install Node 22 from NodeSource:

```bash
sudo apt remove -y libnode-dev libnode72 nodejs npm
sudo apt autoremove -y
sudo apt clean
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
node --version
```

## NodeSource dpkg Overwrite Conflict

Symptom:

```text
trying to overwrite '/usr/include/node/common.gypi',
which is also in package libnode-dev 12.22.9...
```

Cause:

Old Node development packages from Ubuntu remained installed while installing NodeSource Node 22.

Resolution:

Remove old packages:

```bash
sudo apt remove -y libnode-dev libnode72 nodejs npm
sudo apt autoremove -y
sudo apt clean
```

If still needed:

```bash
sudo dpkg -i --force-overwrite /var/cache/apt/archives/nodejs_*nodesource1_amd64.deb
sudo apt -f install -y
```

## GitHub HTTPS Password Authentication Failed

Symptom:

```text
remote: Invalid username or token. Password authentication is not supported for Git operations.
fatal: Authentication failed for 'https://github.com/0Dy6h/medical-resume-tool.git/'
```

Cause:

GitHub no longer accepts account passwords for Git over HTTPS.

Resolution used:

Do not store GitHub credentials on the server. Package the local working tree and upload by `scp`:

```powershell
tar -a -cf medical-resume-tool-deploy.zip @files
scp .\medical-resume-tool-deploy.zip ubuntu@110.42.136.106:/tmp/
```

Alternative future options:

- Use a GitHub personal access token.
- Configure SSH deploy keys.
- Make a CI/CD deployment pipeline.

## PowerShell Zip Flattened Directories

Symptom:

After unzipping, files appeared at the root instead of under `backend/` and `frontend/`, for example:

```text
/opt/medical-resume-tool/main.py
/opt/medical-resume-tool/exporter.py
```

Cause:

The first packaging command flattened paths.

Resolution:

Create the zip with path-preserving `tar` from the project root:

```powershell
$files = git ls-files
tar -a -cf medical-resume-tool-deploy.zip @files
tar -tf medical-resume-tool-deploy.zip | Select-Object -First 40
```

The archive listing must include:

```text
backend/app/main.py
backend/app/services/exporter.py
frontend/src/App.tsx
```

## Permission Denied When Unzipping Under /opt

Symptom:

```text
error: cannot create /opt/medical-resume-tool/...
Permission denied
```

Cause:

`/opt` is owned by root; the `ubuntu` user cannot write there directly.

Resolution:

Use `sudo` for directory creation and unzip, then hand ownership back to `ubuntu`:

```bash
cd /opt
sudo rm -rf /opt/medical-resume-tool
sudo mkdir -p /opt/medical-resume-tool
sudo unzip -o /tmp/medical-resume-tool-deploy.zip -d /opt/medical-resume-tool
sudo chown -R ubuntu:ubuntu /opt/medical-resume-tool
```

## PDF Export Failed for Chinese Text

Symptom:

```text
fpdf.errors.FPDFUnicodeEncodingException:
Character "林" ... is outside the range of characters supported by the font used: "helvetica".
```

Cause:

The original PDF exporter only searched `C:/Windows/Fonts/msyh.ttc`. On Ubuntu it fell back to Helvetica, which cannot encode Chinese text.

Resolution:

Code was updated in:

```text
backend/app/services/exporter.py
```

The exporter now searches common CJK font paths and supports `PDF_FONT_PATH`.

Server font package:

```bash
sudo apt install -y fontconfig fonts-noto-cjk
sudo fc-cache -fv
fc-match "Noto Sans CJK SC"
```

Expected:

```text
NotoSansCJK-Regular.ttc: "Noto Sans CJK SC" "Regular"
```

Verification:

```bash
uv run --project backend pytest -q
```

Result:

```text
42 passed
```

## fc-match Not Found

Symptom:

```text
Command 'fc-match' not found
```

Cause:

`fontconfig` was not installed.

Resolution:

```bash
sudo apt install -y fontconfig fonts-noto-cjk
```

## Server Still Used Old PDF Code

Symptom:

Tests still reported `font used: "helvetica"` after installing fonts.

Cause:

The server still had the old code because the new deployment zip had not been uploaded or extracted correctly.

Resolution:

Confirm the server file contains the fix:

```bash
cd /opt/medical-resume-tool
grep -n "CJK_FONT_CANDIDATES\|PDF_FONT_PATH\|helvetica" backend/app/services/exporter.py
```

Expected:

```text
CJK_FONT_CANDIDATES
PDF_FONT_PATH
```

There should be no old `pdf.set_font("helvetica", size=12)` fallback.

## pnpm Ignored esbuild Build Scripts

Symptom:

```text
[ERR_PNPM_IGNORED_BUILDS] Ignored build scripts: esbuild...
Run "pnpm approve-builds" to pick which dependencies should be allowed to run scripts.
```

Cause:

pnpm 11 blocks dependency build scripts unless approved. Vite/Vitest use `esbuild`.

Resolution:

```bash
cd /opt/medical-resume-tool/frontend
pnpm approve-builds
```

Approve the `esbuild` entries, then rerun:

```bash
pnpm install
pnpm test
pnpm typecheck
pnpm build
```

## API Should Not Expose Port 8000 Publicly

Decision:

FastAPI listens on:

```text
127.0.0.1:8000
```

Nginx exposes:

```text
80
```

Security group should not open `8000`.

Reason:

Nginx provides the public boundary and reverse proxy. Exposing Uvicorn directly increases operational and security risk.

## One-Month Trial Caveats

The site remains reachable at:

```text
http://110.42.136.106/
```

as long as:

- the CVM remains running,
- the trial has not expired,
- the instance has not been released or reinstalled,
- the public IP has not changed,
- Nginx and `medical-resume` are running,
- security group keeps port `80` open.

Before trial expiration, either renew, migrate, or back up the SQLite database and deployment notes.

