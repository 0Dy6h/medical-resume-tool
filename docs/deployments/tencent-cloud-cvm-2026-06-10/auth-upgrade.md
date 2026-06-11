# 多用户登录上线部署说明 — 2026-06-11

本次改动给应用加了**用户名+密码登录 + 按用户隔离**。部署时有两件**必做**的事，否则会出问题。

## 必做 1：设置 AUTH_SECRET（否则重启后所有人需重新登录）

token 用 `AUTH_SECRET` 签名。不设的话进程每次重启会随机生成新密钥，已登录用户的 token 立刻失效。

先生成一段固定随机串（本地或服务器执行一次，记下来）：

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

然后在 systemd service 里加一行 `Environment="AUTH_SECRET=<上面生成的串>"`。完整 service 文件：

```bash
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
Environment="AUTH_SECRET=在这里粘贴你生成的固定随机串"
ExecStart=${UV_PATH} run --project /opt/medical-resume-tool/backend uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl restart medical-resume
```

## 必做 2：重置数据库（表结构变了）

`profiles` / `resume_drafts` 表结构改为按 `user_id`，旧库不兼容。本次约定「清空重来」，所以先备份再删除旧库：

```bash
# 备份（保险）
sudo mkdir -p /opt/backups/medical-resume
sudo cp /opt/medical-resume-tool/backend/data/app.db "/opt/backups/medical-resume/app-before-auth-$(date +%F-%H%M%S).db" 2>/dev/null || true

# 删除旧库，让应用以新结构重建
sudo rm -f /opt/medical-resume-tool/backend/data/app.db
sudo systemctl restart medical-resume
```

岗位库（jobs）也会被清空——重启后到「抓取任务」页跑一次抓取即可重建（岗位是公共数据，不属于任何用户）。

## 完整更新流程

```bash
# 1) 备份并删旧库（见上）
# 2) 解压新代码
cd /opt
sudo unzip -o /tmp/medical-resume-tool-deploy.zip -d /opt/medical-resume-tool
sudo chown -R ubuntu:ubuntu /opt/medical-resume-tool
# 3) 后端依赖 + 测试（本次无新依赖）
cd /opt/medical-resume-tool
uv sync --project backend
uv run --project backend pytest -q          # 期望 59 passed
# 4) 前端构建
cd /opt/medical-resume-tool/frontend
pnpm install
pnpm build
# 5) 更新 systemd（加 AUTH_SECRET，见上），重启
sudo systemctl restart medical-resume
sudo systemctl reload nginx
# 6) 冒烟
curl http://127.0.0.1:8000/health
curl -i http://127.0.0.1/api/profile      # 期望 401（未登录）
```

## 验证

浏览器打开 `http://110.42.136.106/`：
- 未登录 → 自动显示登录/注册页
- 注册 A → 填履历 → 退出 → 注册 B → 看不到 A 的履历
- 抓取任务页跑一次抓取，岗位库恢复数据

## 安全提醒（仍然成立）

- 当前是 **HTTP 明文**，密码和 token 在网络上可被窥探。多人用之前，强烈建议尽快上 HTTPS（需域名 + 证书）。
- 隔离只解决「数据互不干扰」，不等于生产级安全。继续提醒朋友勿填真实敏感信息。
