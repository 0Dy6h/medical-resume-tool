# 云服务器部署清单 — 2026-06-16

## 部署包已准备就绪 ✅

- **部署包：** `medical-resume-tool-deploy-2026-06-16.zip`（仓库根，`git archive HEAD` 产出，含 Stage 3）
- **部署文档：** `docs/deployments/tencent-cloud-cvm-2026-06-16/`（README + deploy.sh）
- **服务器：** `ubuntu@110.42.136.106`，路径 `/opt/medical-resume-tool`，服务 `medical-resume`

## 本次上线：Stage 3 履历导入智能化

无板块标题的简历也能识别事实；导入端点切换到 `build_profile_contract`，按置信度路由到 已识别 / 待确认 / 未归类。**无数据库变更，无需迁移。**

## 快速部署

```bash
# 本地（Windows Git Bash）
scp medical-resume-tool-deploy-2026-06-16.zip ubuntu@110.42.136.106:/tmp/
scp docs/deployments/tencent-cloud-cvm-2026-06-16/deploy.sh ubuntu@110.42.136.106:/tmp/

# 服务器
ssh ubuntu@110.42.136.106
bash /tmp/deploy.sh /tmp/medical-resume-tool-deploy-2026-06-16.zip
```

脚本流程：备份 → 解压 → 检查/装 Tesseract OCR → `uv sync` → `pytest` → `pnpm build` → 重启 → 健康检查。

## 两个前置确认

1. **Tesseract OCR**：deploy.sh 会自动装 `tesseract-ocr tesseract-ocr-chi-sim`；缺失只影响图片/扫描件导入（降级告警），文本类导入不受影响。
2. **若服务器仍是单用户旧版**（未部署过 3ba5dca 的多用户版）：需设 `AUTH_SECRET` + 删旧 `app.db`，见 `docs/deployments/tencent-cloud-cvm-2026-06-10/auth-upgrade.md`；已是多用户版则跳过、保留数据库。

## 验证

http://110.42.136.106/ 登录 → 「我的履历」→ 用**无板块标题**的真实简历导入 → 确认识别出结构化条目，低置信进「待确认」，残余进「未归类原文」。

## 回滚

详见 `docs/deployments/tencent-cloud-cvm-2026-06-16/README.md`（备份目录 `/opt/backups/`）。
