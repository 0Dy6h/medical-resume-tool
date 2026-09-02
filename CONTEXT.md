# CONTEXT — 领域词汇与核心概念

新会话/新贡献者先读本文，再读 `AGENTS.md` 的红线。这些概念在代码中有唯一权威实现位置，不要在别处重新发明。

## 数据可信度分级（A1）

实现：`backend/app/services/repositories.py` 的 `classify_job_trust`。

| 级别 | 含义 |
|---|---|
| `real` | 真实适配器产出且机构当前启用 |
| `placeholder` | generic 占位解析器产出（正文含"该记录由通用列表解析器抽取，需人工复核"），**不得冒充真实数据** |
| `fixture` | 内置演示数据（机构 1-6，`listing_url` 以 `fixture://` 开头） |
| `disabled` | 机构已禁用，其历史数据降级为历史档案 |

岗位库默认视图只展示可信数据；`/api/jobs?trust=` 可切换切片。

## 岗位身份与去重（A4 溯源）

- **岗位身份键 = `(institution_id, source_url)`**。绝不允许按 `source_text_hash` 去重——两家机构转发同一公告是合法共存，不是重复。
- 同一身份重复抓取：内容未变 → 仅刷新 `fetched_at`；内容变化 → 旧正文先归档 `job_snapshots` 再更新现行记录。
- 每条岗位必须可回答：何时（`fetched_at`）、从哪（`source_url`）、谁解析（`parser_name`）、当时正文（`raw_text` / `job_snapshots`）。

## 真实简历约束

- 简历草稿的每一项内容必须锚定 `profile_field_id`（档案字段证据）；无证据内容进入投递版导出会被 409 拦截，除非用户显式 override。
- 「完成审阅」≠「全部采纳」：每个条目必须有 `adopt / edit / remove` 决策。
- 匹配诊断是参考，不是事实来源；学历等硬性门槛不满足会阻断草稿生成（`matching/gates.py`）。

## 抓取与订阅

- **单飞**：手动与自动抓取共用一把执行锁（`crawler.try_acquire_crawl_slot`），同一时间最多一个跑批；自动抓取遇占用跳过本轮，手动遇占用返回 409。
- **每日维护循环**（`scheduler.DailyScheduler`）：每天 09:00（可配）先自动抓取全部启用机构（`crawl_runs.trigger='auto'`），再扫描订阅。
- **零产出 = 失败**：页面抓取成功但解析不出岗位 → `error_type='zero_output'`，疑似站点结构变化，连续失败 ≥2 次机构进入 `review` 状态。
- **出站安全**（`http_client.py`）：TLS 校验强制开启；禁止私网/环回/云元数据地址（含重定向每一跳的 DNS 解析）；单响应上限 10MB。
- **订阅触达**：扫描产生站内通知（`notifications` 表），含新岗位标题摘要；ASCII 关键词按词边界匹配（ICU 不命中 RICU），中文按子串。

## 机构状态

- `institutions.last_status`：`success / failed / review / never`；`review` 表示连续失败需人工复核（配合 `consecutive_failures`）。
- 禁用机构的禁用原因来自 `seeds.BLOCKED_REASONS`（结构化），经 `/api/institutions` 暴露。
- `crawl_strategy`：`fixture / nfyy / z2hospital / bjmu / chinacdc / hrbmu / njmu / generic`；前 6 家 fixture 机构用于离线演示与测试稳定性。
