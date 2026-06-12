# 2026-06-12 部署说明 — 爬虫优化 + profile_import 重构 + UI 改进

本次部署包含自 `3ba5dca`（多用户登录）之后的 8 个新提交，主要改进：

## 本次改动概览

### 1. 爬虫成功率优化 ⭐️
**问题：** 抓取失败率高，常见错误包括 SSL 证书问题、DNS 超时、连接失败

**解决方案：**
- ✅ 所有 httpx 客户端禁用 SSL 验证（`verify=False`）
- ✅ 重试次数：2 → 3 次
- ✅ 超时时间：20s → 30s
- ✅ 重试延迟：0.5s → 1s（指数退避）
- ✅ 扩展重试覆盖：TransportError + TimeoutException + HTTPStatusError

**影响：** 能显著提高医院官网（SSL 配置不规范、网络不稳定）的抓取成功率

### 2. profile_import 重构为模块
- 从单文件 `profile_import.py` 重构为 `profile_import/` 模块
- 清晰分层：extraction（文本提取）→ normalization（规则解析）→ adapter（契约转换）
- 新增契约字段：`review_items`、`unassigned_blocks`、`import_meta`
- 为未来支持 PDF/txt/图片导入做好架构准备

### 3. API 错误处理改进
- 前端 `api.ts` 优化错误消息提取，支持 FastAPI validation 错误格式

### 4. UI 改进
- 登录页重新设计：左右分栏布局（品牌标识 + 特性网格 + 登录表单）
- 文件导入 UI 支持多格式选择（.docx/.pdf/.txt/.md/图片）
- 注：后端当前仅处理 docx，其他格式准备就绪但未启用

### 5. 新增依赖
- `pymupdf`（PDF 文本提取，为未来功能准备）
- `pillow`（图片处理，为未来功能准备）
- `pytesseract`（OCR，为未来功能准备）

注：这些库已添加但功能暂未启用，服务器可选择性安装

## 部署步骤

### 前置条件
- 服务器已部署多用户登录版本（3ba5dca）
- 已设置 `AUTH_SECRET` 环境变量
- 数据库已按用户隔离

### 1. 上传部署包
```bash
# 本地执行
scp medical-resume-tool-deploy-2026-06-12.zip ubuntu@110.42.136.106:/tmp/
```

### 2. 服务器端部署
```bash
# SSH 登录服务器
ssh ubuntu@110.42.136.106

# 备份当前版本
sudo cp -r /opt/medical-resume-tool /opt/backups/medical-resume-tool-$(date +%F-%H%M%S)

# 解压新版本
cd /opt
sudo unzip -o /tmp/medical-resume-tool-deploy-2026-06-12.zip -d /opt/medical-resume-tool
sudo chown -R ubuntu:ubuntu /opt/medical-resume-tool

# 后端依赖同步
cd /opt/medical-resume-tool
uv sync --project backend

# 运行测试验证
uv run --project backend pytest -q
# 期望输出：all tests passed

# 前端构建
cd /opt/medical-resume-tool/frontend
pnpm install
pnpm build

# 重启服务
sudo systemctl restart medical-resume
sudo systemctl reload nginx

# 验证健康状态
curl http://127.0.0.1:8000/health
# 期望输出：{"status":"ok"}
```

### 3. 验证部署

#### 后端验证
```bash
# 健康检查
curl http://110.42.136.106/health

# 认证保护验证
curl -i http://110.42.136.106/api/profile
# 期望：401 Unauthorized

# 查看后端日志
sudo journalctl -u medical-resume -n 50 --no-pager
```

#### 前端验证
浏览器打开 http://110.42.136.106/：
- ✅ 登录页显示新的左右分栏布局
- ✅ 登录后进入工作台
- ✅ 在"我的履历"点击"导入资料"，文件选择器支持多格式（虽然后端只处理 docx）
- ✅ 在"抓取任务"启动一次抓取，观察成功率是否提高

#### 爬虫优化验证
启动一次包含所有 12 个机构的抓取任务，观察：
- 之前失败的机构（中国科学院上海药物研究所、中国中医科学院等）成功率是否提高
- 查看抓取任务详情中的失败原因

## 回滚方案

如果部署后出现问题：

```bash
# 停止服务
sudo systemctl stop medical-resume

# 恢复备份
sudo rm -rf /opt/medical-resume-tool
sudo cp -r /opt/backups/medical-resume-tool-<timestamp> /opt/medical-resume-tool
sudo chown -R ubuntu:ubuntu /opt/medical-resume-tool

# 重启服务
sudo systemctl start medical-resume
```

## 本次提交列表

```
94d7234 docs: update project diagram for 2026-06-12 progress
b91ea0d feat: improve crawler success rate with SSL tolerance and enhanced retry
7ee0fc7 docs: update for profile_import refactoring and UI refresh
09e5587 redesign: refresh login page layout and visual identity
1356089 feat: expand file import UI to accept multiple formats
0e90289 fix: improve error message extraction from API responses
f03c54f build: add dependencies for future PDF/image import support
a014e92 refactor: restructure profile_import as module with enhanced contract
fe266cf docs: refresh beta announcement and principle diagram for auth + docx import
```

## 注意事项

1. **数据兼容性：** 本次部署不涉及数据库表结构变更，无需重置数据库
2. **无需重启 Nginx：** 仅需 `reload` 即可
3. **依赖更新：** 新增了 3 个依赖库，但当前功能未启用，不影响现有功能
4. **爬虫行为变化：** SSL 验证被禁用，更宽容但安全性略降（仅适用于爬取公开页面）
5. **用户体验改进：** 登录页视觉改版，用户可能需要适应新布局

## 后续规划

- [ ] 启用 PDF/txt/markdown 导入（extraction 层已准备好）
- [ ] 启用图片 OCR 导入（需服务器安装 Tesseract）
- [ ] 监控爬虫成功率变化，评估优化效果
- [ ] 考虑添加 HTTPS 支持（需域名和证书）
