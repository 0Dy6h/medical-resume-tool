# 腾讯云 CVM 部署跟进 — 2026-06-18

## Goal

将 2026-06-18 的产品整改成果跟进到腾讯云 CVM：同步最新 `origin/main`，部署到 `/opt/medical-resume-tool`，并完成公网健康检查。

状态：已部署完成。

## Current state

- 仓库：`https://github.com/0Dy6h/medical-resume-tool.git`
- 产品整改提交：`4662c5e [verified] feat: remediate product workflow and evidence UX`
- 服务器记录：`ubuntu@110.42.136.106`
- 应用路径：`/opt/medical-resume-tool`
- systemd 服务：`medical-resume`
- 已部署提交：`1aee7126c46fa4720f2074f8a3e058c7d94fe35e`
- 部署包：仓库根目录 `medical-resume-tool-deploy-2026-06-18.zip`，由 `git archive HEAD` 重新生成
- 公网首页：`http://110.42.136.106/`
- 公网健康检查：`http://110.42.136.106/health`
- 本次备份点：`/opt/backups/medical-resume-tool-2026-06-18-213905`

## Completed in this follow-up

- 确认产品整改提交 `4662c5e8f1c48230d1f48b224706f53f0d51e4f5` 已在 `origin/main` 上。
- 确认部署交接提交 `1aee7126c46fa4720f2074f8a3e058c7d94fe35e` 已在 `origin/main` 上。
- 重新生成 06-18 部署包，并上传到服务器 `/tmp/medical-resume-tool-deploy-2026-06-18.zip`。
- 上传本目录 `deploy.sh` 到服务器 `/tmp/deploy.sh`。
- 执行 `bash /tmp/deploy.sh /tmp/medical-resume-tool-deploy-2026-06-18.zip` 成功。
- 服务器后端测试：`93 passed in 23.97s`。
- 服务器前端构建成功，线上资源更新为：
  - `/assets/index-EmWjHXlN.js`
  - `/assets/index-CdSg1aG4.css`
- systemd `medical-resume` 在 2026-06-18 21:39:45 CST 重启成功。
- 服务器 `/opt/medical-resume-tool/docs/deployments/tencent-cloud-cvm-2026-06-18/README.md` 已存在，确认当前包已落地。
- 确认正确 CVM 是 `110.42.136.106`；旧摘要里出现的 `43.139.19.144` 不是当前部署文档记录的服务器。
- 确认 `http://110.42.136.106/health` 返回 `{"status":"ok"}`。
- 确认 `http://110.42.136.106/` 返回 200，当前线上首页仍可访问。
- 确认 22 端口可达。

## Still open / blocked

已解决。此前当前环境没有被服务器接受的 SSH 凭据，无法实际上传部署包或执行服务器脚本。

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

用户随后在服务器侧补齐授权。本机现在可通过以下命令登录：

```powershell
ssh -i $HOME\.ssh\id_ed25519 -o IdentitiesOnly=yes ubuntu@110.42.136.106 "echo connected"
```

## Deployment commands used

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

已检查：

```bash
curl http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/api/profile
curl http://110.42.136.106/health
```

结果：

- `http://127.0.0.1:8000/health`：`{"status":"ok"}`
- `http://127.0.0.1:8000/api/profile`：`401`
- `http://110.42.136.106/health`：`{"status":"ok"}`
- `http://110.42.136.106/api/jobs?limit=1`：200，返回 `total=245`
- `http://110.42.136.106/api/analytics/summary`：200，返回 `jobs=245`
- `http://110.42.136.106/`：200，引用新构建资源 `/assets/index-EmWjHXlN.js` 和 `/assets/index-CdSg1aG4.css`

浏览器 smoke：

1. 打开 `http://110.42.136.106/`。
2. 注册/登录测试账号。
3. 打开首页/总览、岗位、履历、简历匹配、导出相关路径。
4. 确认 06-18 的首次使用引导、证据链摘要、导出文件名预览等整改已在线上可见。

## Recommended next step

打开 `http://110.42.136.106/` 做一次人工浏览器验收，重点确认首次使用引导、岗位列表、履历导入、简历匹配和导出文件名预览。

## Recommended reading order

1. `docs/handoffs/2026-06-18-product-remediation.md`
2. `docs/plans/2026-06-18-product-remediation-execution.md`
3. `docs/deployments/tencent-cloud-cvm-2026-06-16/README.md`
4. `docs/deployments/tencent-cloud-cvm-2026-06-18/deploy.sh`
