# 部署指南（D1/D2）

从零在一台新服务器/新机器上跑起本系统。与 `docs/runbook.md`（本地开发）互补。

## 1. 前置条件

- Windows：PowerShell 7+（`pwsh`）、[uv](https://docs.astral.sh/uv/)、Node 20+ 与 pnpm（`corepack enable`）
- Linux/macOS：Python 3.12+（uv 可自举）、Node 20+ 与 pnpm
- 出站网络：允许访问各机构官网（HTTP/HTTPS 出站）

## 2. 克隆与依赖

```powershell
git clone <repo-url> medical-job
cd medical-job
uv sync --project backend          # 后端依赖（含 dev）
cd frontend ; pnpm install ; cd ..
```

## 3. 环境变量

全部可选，未设置时使用内置默认。生产建议至少固定 `AUTH_SECRET` 与 `DATABASE_URL`。

| 变量 | 默认 | 说明 |
|---|---|---|
| `AUTH_SECRET` | 未设置时自动生成并持久化到 `data/.auth_secret` | token 签名密钥（D2）。**固定后重启不掉线**；多实例部署必须设同一值 |
| `DATABASE_URL` | `sqlite:///./data/app.db`（相对当前工作目录） | 建议绝对路径，如 `sqlite:////var/lib/medical-job/app.db` |
| `DATA_DIR` | `data` | `.auth_secret` 的落盘目录 |
| `AUTO_CRAWL_ENABLED` | `true` | 每日自动抓取开关（A3） |
| `SUBSCRIPTION_SCAN_ENABLED` | `true` | 每日订阅扫描开关 |
| `SUBSCRIPTION_SCAN_HOUR` / `_MINUTE` | `9` / `0` | 每日维护循环时间（本地时区） |
| `CRAWL_TIMEOUT` | `30` | 单请求超时（秒） |
| `CRAWL_RETRIES` | `3` | 网络错误重试次数（指数退避） |
| `CRAWL_DELAY_SECONDS` | `1` | 机构间抓取间隔 |
| `JOB_LIST_MAX_LIMIT` | `500` | `/api/jobs` 单页上限 |

> 密钥文件 `data/.auth_secret` 由应用自动创建（POSIX 下 0600），**不要提交到版本库**；
> `data/` 目录整体应包含在备份策略中（含数据库与密钥）。

## 4. 启动

### 本地/单机（Windows）

```powershell
pwsh -NoProfile -File scripts/start-local.ps1            # 前台启动 + 健康自检
pwsh -NoProfile -File scripts/start-local.ps1 -NoBrowser # 不开浏览器
pwsh -NoProfile -File scripts/start-local.ps1 -Stop      # 停止
```

### 手动（Linux/macOS 同理）

```bash
# 后端（工作目录必须在 backend/）
cd backend
uv run --project . python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 前端：开发模式仅限本机调试；生产用构建产物
cd frontend && pnpm build
pnpm preview --host 0.0.0.0 --port 5173   # 或用 nginx 托管 dist/
```

## 5. HTTPS 反向代理（D2）

应用本身只提供 HTTP；对外服务必须置于 TLS 反代之后（nginx / Caddy / IIS 均可）：

```nginx
server {
    listen 443 ssl;
    server_name jobs.example.com;
    ssl_certificate     /etc/letsencrypt/live/jobs.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/jobs.example.com/privkey.pem;

    location /api/ { proxy_pass http://127.0.0.1:8000; proxy_set_header Host $host; }
    location /    { proxy_pass http://127.0.0.1:5173; proxy_set_header Host $host; }
}
```

CORS 白名单只放行了 `localhost:5173`；经域名访问时无需额外配置（同源反代），
如需跨域请同步修改 `backend/app/main.py` 的 `allow_origins`。

## 6. PDF 导出中文字体（D1）

服务器无中文字体时 PDF 会出现方块/缺字：

- Debian/Ubuntu：`apt install fonts-noto-cjk`
- Windows Server：自带微软雅黑，无需处理
- 容器化：在镜像中安装 Noto CJK 后再启动

## 7. 部署验收清单

1. `GET /health` 返回 `{"status":"ok"}`
2. 注册 → 登录 → **重启后端** → 刷新页面仍处于登录态（验证 D2 密钥固定）
3. 抓取任务页启动 12 家机构跑批 → 状态 completed / partial，失败项有可见原因
4. 任选真实机构岗位 → 生成草稿 → 审阅 → 导出 DOCX 与 PDF（中文正常、无豆腐块）
5. 订阅一个关键词 → 手动扫描 → 顶栏铃铛出现通知
6. 匿名 `POST /api/crawl-runs` 返回 401
