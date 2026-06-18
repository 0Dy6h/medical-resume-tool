# 腾讯云 CVM 部署跟进 — 2026-06-18

## Goal

将 2026-06-18 的产品整改成果跟进到腾讯云 CVM：同步最新 `origin/main`，部署到 `/opt/medical-resume-tool`，并完成公网健康检查。

## Current state

- 仓库：`https://github.com/0Dy6h/medical-resume-tool.git`
- 产品整改提交：`4662c5e [verified] feat: remediate product workflow and evidence UX`
- 服务器记录：`ubuntu@110.42.136.106`
- 应用路径：`/opt/medical-resume-tool`
- systemd 服务：`medical-resume`
- 部署包：仓库根目录 `medical-resume-tool-deploy-2026-06-18.zip`
- 公网首页：`http://110.42.136.106/`
- 公网健康检查：`http://110.42.136.106/health`

## Completed in this follow-up

- 确认产品整改提交 `4662c5e8f1c48230d1f48b224706f53f0d51e4f5` 已在 `origin/main` 上。
- 确认 06-18 部署包已存在于仓库根目录。
- 确认正确 CVM 是 `110.42.136.106`；旧摘要里出现的 `43.139.19.144` 不是当前部署文档记录的服务器。
- 确认 `http://110.42.136.106/health` 返回 `{"status":"ok"}`。
- 确认 `http://110.42.136.106/` 返回 200，当前线上首页仍可访问。
- 确认 22 端口可达。

## Still open / blocked

当前环境没有被服务器接受的 SSH 凭据，无法实际上传部署包或执行服务器脚本。

已验证失败的登录方式：

```powershell
ssh -o BatchMode=yes -o ConnectTimeout=10 ubuntu@110.42.136.106 "echo connected"
ssh -i $HOME\.ssh\id_ed25519 -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10 ubuntu@110.42.136.106 "echo connected"
ssh -o BatchMode=yes -o ConnectTimeout=10 root@110.42.136.106 "echo connected"
```

返回均为：

```text
Permission denied (publickey,password).
```

本机存在 `C:\Users\12035\.ssh\id_ed25519.pub`，但该公钥当前没有被服务器授权。需要先在腾讯云控制台重置/确认登录方式，或把该公钥追加到服务器 `ubuntu` 用户的 `~/.ssh/authorized_keys`。

## Deployment commands after SSH is fixed

在本地 PowerShell / Git Bash 中执行：

```bash
scp medical-resume-tool-deploy-2026-06-18.zip ubuntu@110.42.136.106:/tmp/
scp docs/deployments/tencent-cloud-cvm-2026-06-18/deploy.sh ubuntu@110.42.136.106:/tmp/
ssh ubuntu@110.42.136.106
bash /tmp/deploy.sh /tmp/medical-resume-tool-deploy-2026-06-18.zip
```

`deploy.sh` 会执行：

- 备份现有 `/opt/medical-resume-tool` 到 `/opt/backups/`
- 解压新版本到 `/opt/medical-resume-tool`
- 检查/安装 Tesseract OCR
- `uv sync --project backend --all-groups`
- `uv run --project backend pytest -q`
- `pnpm install --frozen-lockfile`
- `pnpm build`
- `sudo systemctl restart medical-resume`
- `sudo systemctl reload nginx`
- `curl http://127.0.0.1:8000/health`
- `curl http://127.0.0.1:8000/api/profile`，期望返回 `401`

## Verification after deploy

部署完成后至少检查：

```bash
curl http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/api/profile
curl http://110.42.136.106/health
```

浏览器 smoke：

1. 打开 `http://110.42.136.106/`。
2. 注册/登录测试账号。
3. 打开首页/总览、岗位、履历、简历匹配、导出相关路径。
4. 确认 06-18 的首次使用引导、证据链摘要、导出文件名预览等整改已在线上可见。

## Recommended next step

先恢复 SSH 权限，然后直接运行本目录的 `deploy.sh`。如果只是临时演示，也可以从腾讯云网页终端登录服务器后，用 `/tmp` 上传同名 zip 和脚本再执行。

## Recommended reading order

1. `docs/handoffs/2026-06-18-product-remediation.md`
2. `docs/plans/2026-06-18-product-remediation-execution.md`
3. `docs/deployments/tencent-cloud-cvm-2026-06-16/README.md`
4. `docs/deployments/tencent-cloud-cvm-2026-06-18/deploy.sh`
