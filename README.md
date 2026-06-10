# 医疗岗位情报与真实简历定制工具

本项目是一个本地运行的 MVP：抓取公开官网招聘岗位，做岗位分类、标签与市场分析，并基于用户提供的真实结构化履历生成定制简历草稿，支持 DOCX/PDF 导出。

## 当前能力

- 30 家中国大陆医疗相关机构种子，其中 12 家当前启用：前 6 家内置本地演示 fixture，另有 6 家公开官网真实适配器。
- FastAPI + SQLite 后端，提供计划中的核心 REST API。
- React/Vite 工作台：总览、岗位库、分析、我的履历、简历生成、抓取任务。
- 规则化岗位抽取、去重、标签、分析报告，并支持从公开官网公告的 xlsx 附件中抽取岗位表。
- 分析页提供解析器质量 review：按 `parser_name` 聚合岗位量、平均置信度、附件来源、低置信和附件失败事件。
- 岗位详情保留来源证据：`source_url`、`source_text_hash`、`fetched_at`、`parser_name`，附件解析岗位还保留公告 URL、附件 URL、sheet 和行号。
- 真实履历约束：简历草稿的强化表达只来自用户结构化字段，并展示匹配证据和缺口。
- DOCX/PDF 导出端点。

## 项目文档

- 架构说明：`docs/architecture.md`
- 运维/启动手册：`docs/runbook.md`
- Agent 接手规则：`AGENTS.md`
- 当前交接：`docs/handoffs/2026-06-09-attachment-aware-data-loop.md`

## 后端

```powershell
uv run --project backend pytest -q
uv run --project backend uvicorn app.main:app --host 127.0.0.1 --port 8000
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
