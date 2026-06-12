# 云服务器部署清单 — 2026-06-12

## 部署包已准备就绪 ✅

**部署包位置：** `medical-resume-tool-deploy-2026-06-12.zip` (390KB)

**GitHub 位置：** 
- 仓库：https://github.com/0Dy6h/medical-resume-tool
- 部署文档：`docs/deployments/tencent-cloud-cvm-2026-06-12/`

## 快速部署指南

### 步骤 1：上传部署包到服务器

```bash
# 本地执行（Windows Git Bash）
scp medical-resume-tool-deploy-2026-06-12.zip ubuntu@110.42.136.106:/tmp/
```

### 步骤 2：SSH 登录服务器并执行部署

```bash
# 登录服务器
ssh ubuntu@110.42.136.106

# 下载并执行部署脚本
cd /tmp
curl -O https://raw.githubusercontent.com/0Dy6h/medical-resume-tool/main/docs/deployments/tencent-cloud-cvm-2026-06-12/deploy.sh
bash deploy.sh /tmp/medical-resume-tool-deploy-2026-06-12.zip
```

**或者手动部署（如果脚本不可用）：**

```bash
# 备份当前版本
sudo cp -r /opt/medical-resume-tool /opt/backups/medical-resume-tool-$(date +%F-%H%M%S)

# 解压新版本
cd /opt
sudo unzip -o /tmp/medical-resume-tool-deploy-2026-06-12.zip -d /opt/medical-resume-tool
sudo chown -R ubuntu:ubuntu /opt/medical-resume-tool

# 同步依赖
cd /opt/medical-resume-tool
uv sync --project backend

# 运行测试
uv run --project backend pytest -q

# 构建前端
cd /opt/medical-resume-tool/frontend
pnpm install
pnpm build

# 重启服务
sudo systemctl restart medical-resume
sudo systemctl reload nginx

# 验证
curl http://127.0.0.1:8000/health
```

### 步骤 3：验证部署

1. **浏览器验证：** http://110.42.136.106/
   - 检查登录页是否显示新的左右分栏布局
   - 登录后功能正常

2. **爬虫验证：**
   - 进入「抓取任务」页面
   - 启动一次包含所有 12 个机构的抓取
   - 观察之前失败的机构（中国科学院上海药物研究所、中国中医科学院）是否成功率提高

3. **后端日志：**
   ```bash
   sudo journalctl -u medical-resume -f
   ```

## 本次改动概要

### 核心改进
1. **爬虫成功率优化** ⭐️
   - SSL 验证禁用（容忍自签名证书）
   - 重试次数：2 → 3
   - 超时时间：20s → 30s
   - 预期效果：显著降低 SSL 和网络失败率

2. **profile_import 重构**
   - 模块化架构（extraction/normalization/adapter）
   - 新增质量反馈字段
   - 为多格式导入做准备

3. **UI 改进**
   - 登录页重新设计（左右分栏）
   - 文件导入界面支持多格式选择

4. **API 错误处理改进**
   - 更友好的错误消息提取

### 重要说明
- ✅ **数据库兼容** - 无需重置，所有数据保留
- ✅ **API 兼容** - 向后兼容，无破坏性变更
- ⚠️ **SSL 验证禁用** - 仅影响爬虫，不影响用户访问安全
- 📦 **新增依赖** - pymupdf, pillow, pytesseract（功能未启用）

## 回滚方案

如果部署后发现问题：

```bash
# 停止服务
sudo systemctl stop medical-resume

# 找到最近的备份
ls -lt /opt/backups/ | head -5

# 恢复备份（替换 <timestamp> 为实际时间戳）
sudo rm -rf /opt/medical-resume-tool
sudo cp -r /opt/backups/medical-resume-tool-<timestamp> /opt/medical-resume-tool
sudo chown -R ubuntu:ubuntu /opt/medical-resume-tool

# 重启服务
sudo systemctl start medical-resume
```

## 联系信息

- **服务器 IP：** 110.42.136.106
- **SSH 用户：** ubuntu
- **应用路径：** /opt/medical-resume-tool
- **服务名称：** medical-resume
- **数据库：** /opt/medical-resume-tool/backend/data/app.db

## 详细文档

完整部署文档请查看：
- `docs/deployments/tencent-cloud-cvm-2026-06-12/README.md` - 完整部署指南
- `docs/deployments/tencent-cloud-cvm-2026-06-12/CHANGELOG.md` - 详细更新日志
- `docs/deployments/tencent-cloud-cvm-2026-06-12/deploy.sh` - 自动化部署脚本

---

**准备就绪！随时可以部署到云服务器。** 🚀
