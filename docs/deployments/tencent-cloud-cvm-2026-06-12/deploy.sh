#!/bin/bash
# 2026-06-12 部署脚本 — 在服务器上执行
# 使用方法：bash deploy.sh /tmp/medical-resume-tool-deploy-2026-06-12.zip

set -e  # 遇到错误立即退出

DEPLOY_ZIP="${1:-/tmp/medical-resume-tool-deploy-2026-06-12.zip}"
INSTALL_DIR="/opt/medical-resume-tool"
BACKUP_DIR="/opt/backups/medical-resume-tool-$(date +%F-%H%M%S)"

echo "=== 医疗简历工具 2026-06-12 部署脚本 ==="
echo ""

# 检查部署包
if [ ! -f "$DEPLOY_ZIP" ]; then
    echo "错误：部署包不存在 $DEPLOY_ZIP"
    echo "请先上传：scp medical-resume-tool-deploy-2026-06-12.zip ubuntu@110.42.136.106:/tmp/"
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

# 解压新版本
echo ">>> 2. 解压新版本..."
cd /opt
sudo unzip -o "$DEPLOY_ZIP" -d "$INSTALL_DIR"
sudo chown -R ubuntu:ubuntu "$INSTALL_DIR"
echo "✓ 解压完成"
echo ""

# 后端依赖同步
echo ">>> 3. 同步后端依赖..."
cd "$INSTALL_DIR"
uv sync --project backend
echo "✓ 依赖同步完成"
echo ""

# 运行测试
echo ">>> 4. 运行测试..."
uv run --project backend pytest -q
echo "✓ 测试通过"
echo ""

# 前端构建
echo ">>> 5. 构建前端..."
cd "$INSTALL_DIR/frontend"
pnpm install --frozen-lockfile
pnpm build
echo "✓ 前端构建完成"
echo ""

# 重启服务
echo ">>> 6. 重启服务..."
sudo systemctl restart medical-resume
sleep 2
sudo systemctl reload nginx
echo "✓ 服务已重启"
echo ""

# 健康检查
echo ">>> 7. 健康检查..."
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
echo "2. 检查登录页是否显示新的左右分栏布局"
echo "3. 登录后进入工作台"
echo "4. 在「抓取任务」启动一次抓取，观察成功率"
echo ""
echo "如需回滚："
echo "  sudo systemctl stop medical-resume"
echo "  sudo rm -rf $INSTALL_DIR"
echo "  sudo cp -r $BACKUP_DIR $INSTALL_DIR"
echo "  sudo chown -R ubuntu:ubuntu $INSTALL_DIR"
echo "  sudo systemctl start medical-resume"
echo ""
