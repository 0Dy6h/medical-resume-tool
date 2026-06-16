# 腾讯云 CVM 部署 — 2026-06-16

本次上线内容：**Stage 3 履历导入智能化**（无板块标题的简历也能识别事实）。

- 仓库：https://github.com/0Dy6h/medical-resume-tool
- 服务器：`ubuntu@110.42.136.106`，应用路径 `/opt/medical-resume-tool`，服务名 `medical-resume`
- 部署包：`medical-resume-tool-deploy-2026-06-16.zip`（仓库根，`git archive HEAD` 产出）

## 本次改动

- 导入端点从 heading-only 解析器切换到事实抽取管线（`build_profile_contract`）：
  - 按实体信号识别 education/experiences/projects/certificates/languages/skills 等，**不再依赖板块标题**。
  - 置信度路由：`>=0.75` 自动结构化、`0.45-0.75` 进「待确认」(`review_items`)、更低进「未归类原文」(`unassigned_blocks`)。
- 前端「我的履历」导入预览新增「待确认」（默认不勾选）和「未归类原文」两个区。
- 提取层（DOCX/PDF/TXT/MD/图片+OCR）未改动。

**兼容性**：无数据库结构变更（导入是无状态的，不落库），**无需迁移、无需重置数据库**。后端无新增 Python 依赖。

## 部署步骤

```bash
# 1) 本地（Windows Git Bash）上传部署包
scp medical-resume-tool-deploy-2026-06-16.zip ubuntu@110.42.136.106:/tmp/
scp docs/deployments/tencent-cloud-cvm-2026-06-16/deploy.sh ubuntu@110.42.136.106:/tmp/

# 2) 登录服务器执行
ssh ubuntu@110.42.136.106
bash /tmp/deploy.sh /tmp/medical-resume-tool-deploy-2026-06-16.zip
```

`deploy.sh` 会：备份 → 解压 → 检查/安装 Tesseract OCR → `uv sync` → `pytest` → `pnpm build` → 重启服务 → 健康检查。

## 两个前置确认（重要）

1. **Tesseract OCR**：图片/扫描件导入依赖本机 `tesseract` 二进制 + 中文语言包。`deploy.sh` 第 3 步会自动安装 `tesseract-ocr tesseract-ocr-chi-sim`。若不需要图片导入，缺失也只会让图片/扫描件导入降级为告警，**文本类（DOCX/文本型 PDF/TXT/MD）导入不受影响**。

2. **首次部署多用户版本时**（若服务器当前仍是 3ba5dca 之前的单用户版本，未做过 auth 升级）：
   - systemd 设置 `AUTH_SECRET`（已生成串见 `../tencent-cloud-cvm-2026-06-10/auth-upgrade.md`）。
   - 删除旧 `backend/data/app.db`（表结构已变）。
   - 若服务器**已经是**多用户版本（已部署过 3ba5dca 或之后），则**跳过本条**，保留数据库。

## 验证

1. 浏览器打开 http://110.42.136.106/ 并登录。
2. 进入「我的履历」，用一份**没有板块标题**的真实简历（PDF/DOCX/TXT）导入。
3. 期望：能识别教育/工作/项目等结构化条目；低置信项落「待确认」；未识别原文落「未归类原文」可查看。

## 回滚

```bash
sudo systemctl stop medical-resume
ls -lt /opt/backups/ | head -5            # 找最近备份
sudo rm -rf /opt/medical-resume-tool
sudo cp -r /opt/backups/medical-resume-tool-<timestamp> /opt/medical-resume-tool
sudo chown -R ubuntu:ubuntu /opt/medical-resume-tool
sudo systemctl start medical-resume
```

## 已知边界（v1 规则抽取）

事实抽取是规则化 v1，已在理想样例验证通过，真实简历可能需迭代：含「项目/课题」的块可能优先判为 project；部分技能词表偏宽。低置信项不会自动导入，统一进「待确认」由用户裁决，是有意的保守设计。详见 `backend/app/services/profile_import/HANDOFF.md`。
