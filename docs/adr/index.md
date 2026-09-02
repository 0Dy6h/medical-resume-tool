# ADR 索引

架构决策记录。当某个选择会让未来贡献者"意外"时（为什么不用 X？为什么强制 Y？），在此落一条。

现有核心决策目前以红线形式写在 `AGENTS.md`、以词汇表形式写在 `CONTEXT.md`，
后续新决策请按 `YYYY-MM-DD-<slug>.md` 命名落进本目录，并在下表登记。

| 日期 | 决策 | 状态 | 详细 |
|---|---|---|---|
| 2026-06 | 岗位身份键 = (institution_id, source_url)，禁止按正文哈希去重 | 已采纳（红线） | `CONTEXT.md` 岗位身份节；迁移实现 `database._migrate_jobs_identity_key` |
| 2026-06 | 简历内容逐项绑定档案证据，无证据内容导出硬拦截 | 已采纳（红线） | `CONTEXT.md` 真实简历约束节 |
| 2026-06 | 只采集公开官网，不接第三方平台登录、不做反爬对抗 | 已采纳（红线） | `AGENTS.md` Core Boundaries |
| 2026-06 | LLM 不作为核心匹配/简历生成依赖（仅用于按需 JD 结构化，失败可降级） | 已采纳 | `backend/app/services/jd_structurer.py` |
| 2026-08 | PDF 附件仅记录为证据，不做表格解析（除非带 fixture 与测试） | 已采纳（红线） | `AGENTS.md` |
| 2026-09 | 出站抓取强制 TLS 校验 + 私网/元数据拦截 + 10MB 上限 | 已采纳 | `backend/app/services/http_client.py` |
| 2026-09 | AUTH_SECRET 未设置时落盘 data/.auth_secret 而非进程内随机 | 已采纳 | `backend/app/services/auth.py` |
| 2026-09 | 零产出视为失败并计数，连续失败进入 review 状态 | 已采纳 | `repositories.mark_institution` |
