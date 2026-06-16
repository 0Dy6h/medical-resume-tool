#!/bin/bash
# 2026-06-16 部署脚本 — 在服务器上执行
# 使用方法：bash deploy.sh /tmp/medical-resume-tool-deploy-2026-06-16.zip

set -e  # 遇到错误立即退出

# 非交互式 SSH（ssh host 'bash deploy.sh'）不加载 ~/.profile / ~/.bashrc，
# 而 uv 装在 ~/.local/bin，不在默认 PATH。systemd 服务用 uv 绝对路径不受影响，
# 但脚本里的 uv sync / uv run 会 command not found，故在此手动补上。
export PATH="$HOME/.local/bin:$PATH"

DEPLOY_ZIP="${1:-/tmp/medical-resume-tool-deploy-2026-06-16.zip}"
INSTALL_DIR="/opt/medical-resume-tool"
BACKUP_DIR="/opt/backups/medical-resume-tool-$(date +%F-%H%M%S)"

echo "=== 医疗简历工具 2026-06-16 部署脚本（Stage 3 履历导入智能化）==="
echo ""

# 检查部署包
if [ ! -f "$DEPLOY_ZIP" ]; then
    echo "错误：部署包不存在 $DEPLOY_ZIP"
    echo "请先上传：scp medical-resume-tool-deploy-2026-06-16.zip ubuntu@110.42.136.106:/tmp/"
    exit 1
fi
echo "✓ 部署包：$DEPLOY_ZIP"
echo ""

# 备份当前版本
echo ">>> 1. 备份当前版本..."
if [ -d "$INSTALL_DIR" ]; then
    sudo mkdir -p /opt/backups
    sudo cp -r "$INSTALL_DIR" "$BACKUP_DIR"
    echo "✓ 已备份到：$BACKUP_DIR"
else
    echo "! 未找到现有安装，跳过备份"
fi
echo ""

# 解压新版本（保留 backend/data 下的数据库）
echo ">>> 2. 解压新版本..."
cd /opt
sudo unzip -o "$DEPLOY_ZIP" -d "$INSTALL_DIR"
sudo chown -R ubuntu:ubuntu "$INSTALL_DIR"
echo "✓ 解压完成"
echo ""

# Tesseract OCR（图片/扫描件导入需要；缺失时导入会降级为告警，不影响文本类导入）
echo ">>> 3. 检查 Tesseract OCR..."
if command -v tesseract >/dev/null 2>&1; then
    echo "✓ 已安装：$(tesseract --version 2>&1 | head -1)"
else
    echo "! 未安装 Tesseract，开始安装中文+英文语言包..."
    sudo apt-get update
    sudo apt-get install -y tesseract-ocr tesseract-ocr-chi-sim
    echo "✓ Tesseract 安装完成"
fi
echo ""

# 后端依赖同步（Stage 3 无新增依赖；pymupdf/pillow/pytesseract 已在 pyproject）
echo ">>> 4. 同步后端依赖..."
cd "$INSTALL_DIR"
uv sync --project backend
echo "✓ 依赖同步完成"
echo ""

# 运行测试
echo ">>> 5. 运行测试..."
uv run --project backend pytest -q
echo "✓ 测试通过"
echo ""

# 前端构建
echo ">>> 6. 构建前端..."
cd "$INSTALL_DIR/frontend"
pnpm install --frozen-lockfile
pnpm build
echo "✓ 前端构建完成"
echo ""

# 重启服务
echo ">>> 7. 重启服务..."
sudo systemctl restart medical-resume
sleep 2
sudo systemctl reload nginx
echo "✓ 服务已重启"
echo ""

# 健康检查
echo ">>> 8. 健康检查..."
HEALTH_CHECK=$(curl -s http://127.0.0.1:8000/health || echo "FAILED")
if echo "$HEALTH_CHECK" | grep -q '"status":"ok"'; then
    echo "✓ 后端健康检查通过"
else
    echo "✗ 后端健康检查失败：$HEALTH_CHECK"
    echo ""
    echo "查看日志："
    sudo journalctl -u medical-resume -n 20 --no-pager
    exit 1
fi

AUTH_CHECK=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/profile)
if [ "$AUTH_CHECK" = "401" ]; then
    echo "✓ 认证保护正常"
else
    echo "! 认证检查返回：$AUTH_CHECK（期望 401）"
fi
echo ""

# 完成
echo "=== 部署完成 ==="
echo ""
echo "验证步骤："
echo "1. 浏览器打开：http://110.42.136.106/"
echo "2. 登录后进入「我的履历」"
echo "3. 用一份【没有板块标题】的真实简历（PDF/DOCX/TXT）导入"
echo "4. 确认能识别出教育/工作/项目等条目，低置信项进「待确认」，残余进「未归类原文」"
echo ""
echo "如需回滚："
echo "  sudo systemctl stop medical-resume"
echo "  sudo rm -rf $INSTALL_DIR"
echo "  sudo cp -r $BACKUP_DIR $INSTALL_DIR"
echo "  sudo chown -R ubuntu:ubuntu $INSTALL_DIR"
echo "  sudo systemctl start medical-resume"
echo ""
