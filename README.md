# 医疗岗位情报与真实简历定制工具

本项目是一个本地运行的 MVP：抓取公开官网招聘岗位，做岗位分类、标签与市场分析，并基于用户提供的真实结构化履历生成定制简历草稿，支持 DOCX/PDF 导出。

## 当前能力

- 30 家中国大陆医疗相关机构种子，其中 12 家当前启用：前 6 家内置本地演示 fixture，另有 6 家公开官网真实适配器。
- 每日 09:00 自动抓取全部启用机构并扫描订阅推送（单飞互斥、失败留痕、连续失败进入需复核状态）；抓取支持一键重跑。
- 订阅新岗位产生站内通知（顶栏铃铛），含新岗位标题摘要；英文关键词按词边界匹配。
- FastAPI + SQLite 后端，提供计划中的核心 REST API。
- React/Vite 工作台：总览、岗位库、分析、我的履历、简历生成、抓取任务。
- 规则化岗位抽取、去重、标签、分析报告，并支持从公开官网公告的 xlsx 附件中抽取岗位表。
- 分析页提供解析器质量 review：按 `parser_name` 聚合岗位量、平均置信度、附件来源、低置信和附件失败事件。
- 岗位详情保留来源证据：`source_url`、`source_text_hash`、`fetched_at`、`parser_name`，附件解析岗位还保留公告 URL、附件 URL、sheet 和行号。
- 真实履历约束：简历草稿只重排用户填写的字段，不改写、不编造；每条证据锚定到 `profile_field_id`。
- 语义化的岗位匹配：先从公告中切分出真正的岗位要求（丢弃报名流程与机构自我介绍），再用中文二元分词 + IDF 加权做证据匹配；学历这类有序要求用算术门槛判定，学历不满足会给出“硬性条件不满足”的阻断提示，而不是照样生成简历。
- “我的履历”包含个人信息（姓名/联系方式/求职意向），并支持从 DOCX、文本型 PDF、TXT、Markdown 和常见图片导入资料；图片/扫描 PDF 的文字识别依赖本机 Tesseract OCR。
- DOCX/PDF 导出端点：DOCX 由 python-docx 生成，简历以个人信息抬头（姓名+联系方式）开头，可直接投递。

## 项目文档

- 架构说明：`docs/architecture.md`
- 领域词汇与核心概念：`CONTEXT.md`
- 运维/启动手册（本地开发）：`docs/runbook.md`
- 服务器部署指南：`docs/deploy.md`
- Agent 接手规则：`AGENTS.md`
- 当前交接：`docs/handoffs/2026-09-02-workspace-and-startup.md`
- 架构决策记录：`docs/adr/index.md`
- 历史线上部署记录：`docs/deployments/tencent-cloud-cvm-2026-06-18/README.md`

## 后端

```powershell
uv run --project backend pytest -q
cd backend; uv run --project . python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

## 前端

```powershell
cd frontend
pnpm install
pnpm test
pnpm typecheck
pnpm build
pnpm dev
```

打开：

```text
http://127.0.0.1:5173
```

## 本地一键启动（推荐）

```powershell
pwsh -NoProfile -File scripts/start-local.ps1        # 启动：装依赖(非交互) + 起前后端 + 健康自检 + 开浏览器
pwsh -NoProfile -File scripts/start-local.ps1 -Stop  # 停止服务（按 PID 文件 + 进程树）
```

日志写入 `logs/`，数据库为 `backend/data/app.db`。详见 `docs/runbook.md`。

## MVP 使用顺序

1. 启动后端和前端。
2. 打开“抓取任务”，选择前 6 个 fixture 机构做稳定演示，或选择 12 个启用机构测试真实适配器。
3. 在“岗位库”查看岗位详情、标签、来源快照和附件级来源证据。
4. 在“分析”查看岗位方向、学历要求、共性能力，并生成报告。
5. 在“我的履历”填写结构化事实，或载入示例后保存。
6. 在“简历生成”选择目标岗位，生成草稿，检查证据和缺口，导出 DOCX/PDF。

## 重要边界

- MVP 不接第三方招聘平台账号，不绕登录，不做反爬对抗。
- 通用官网解析器会保留来源和解析器信息，真实投产前需要对高价值机构逐个加专用适配器并做人工抽样质检。
- PDF 附件当前只做发现和证据记录，不做表格解析。
- 岗位分析只代表当前样本，不声称覆盖完整市场。
- 简历生成只重组用户提供过的事实，不自动创造经历、项目、证书或成果。
