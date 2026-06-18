#!/bin/bash
# 2026-06-18 deployment script for Tencent Cloud CVM.
# Usage on server:
#   bash deploy.sh /tmp/medical-resume-tool-deploy-2026-06-18.zip

set -e

# Non-interactive SSH sessions do not load ~/.profile. uv is installed there.
export PATH="$HOME/.local/bin:$PATH"

DEPLOY_ZIP="${1:-/tmp/medical-resume-tool-deploy-2026-06-18.zip}"
INSTALL_DIR="/opt/medical-resume-tool"
BACKUP_DIR="/opt/backups/medical-resume-tool-$(date +%F-%H%M%S)"

echo "=== medical-resume-tool 2026-06-18 deployment ==="
echo ""

if [ ! -f "$DEPLOY_ZIP" ]; then
    echo "ERROR: deployment package not found: $DEPLOY_ZIP"
    echo "Upload it first:"
    echo "  scp medical-resume-tool-deploy-2026-06-18.zip ubuntu@110.42.136.106:/tmp/"
    exit 1
fi

echo "Package: $DEPLOY_ZIP"
echo ""

echo ">>> 1. Back up current install..."
if [ -d "$INSTALL_DIR" ]; then
    sudo mkdir -p /opt/backups
    sudo cp -r "$INSTALL_DIR" "$BACKUP_DIR"
    echo "Backup: $BACKUP_DIR"
else
    echo "No existing install found; skipping backup."
fi
echo ""

echo ">>> 2. Extract new version..."
cd /opt
sudo unzip -o "$DEPLOY_ZIP" -d "$INSTALL_DIR"
sudo chown -R ubuntu:ubuntu "$INSTALL_DIR"
echo "Extracted to $INSTALL_DIR"
echo ""

echo ">>> 3. Check Tesseract OCR..."
if command -v tesseract >/dev/null 2>&1; then
    tesseract --version 2>&1 | head -1
else
    echo "Tesseract is missing; installing Chinese/English OCR packages..."
    sudo apt-get update
    sudo apt-get install -y tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-eng
fi
echo ""

echo ">>> 4. Sync backend dependencies..."
cd "$INSTALL_DIR"
uv sync --project backend --all-groups
echo ""

echo ">>> 5. Run backend tests..."
uv run --project backend pytest -q
echo ""

echo ">>> 6. Build frontend..."
cd "$INSTALL_DIR/frontend"
pnpm install --frozen-lockfile
pnpm build
echo ""

echo ">>> 7. Restart services..."
sudo systemctl restart medical-resume
sleep 2
sudo nginx -t
sudo systemctl reload nginx
echo ""

echo ">>> 8. Health checks..."
HEALTH_CHECK="$(curl -s http://127.0.0.1:8000/health || echo FAILED)"
if echo "$HEALTH_CHECK" | grep -q '"status":"ok"'; then
    echo "Backend health OK"
else
    echo "Backend health failed: $HEALTH_CHECK"
    sudo journalctl -u medical-resume -n 40 --no-pager
    exit 1
fi

AUTH_CHECK="$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/profile)"
if [ "$AUTH_CHECK" = "401" ]; then
    echo "Auth guard OK"
else
    echo "Auth guard returned $AUTH_CHECK; expected 401."
fi

PUBLIC_HEALTH="$(curl -s http://110.42.136.106/health || echo FAILED)"
echo "Public health: $PUBLIC_HEALTH"

echo ""
echo "=== Deployment complete ==="
echo "Open http://110.42.136.106/ and smoke test onboarding, jobs, profile, resume matching, and export."
echo ""
echo "Rollback, if needed:"
echo "  sudo systemctl stop medical-resume"
echo "  sudo rm -rf $INSTALL_DIR"
echo "  sudo cp -r $BACKUP_DIR $INSTALL_DIR"
echo "  sudo chown -R ubuntu:ubuntu $INSTALL_DIR"
echo "  sudo systemctl start medical-resume"
