# traework 4.1 订阅自动推送切片评审 — 2026-08-22（commit 818ff5d）

## 结论：有条件通过（无 P0/P1 阻塞）

推送/已读解耦、维护中排除、crawl 后自动触发、可注入时钟调度器均按提示词落地，门禁全绿。
以下 minor 不阻塞合并，建议后续顺手修。

## 实测门禁（本沙箱实际运行）

- 后端：`uv run --project backend pytest -q` → **241 passed**（87.1s，231 基线 + 10 新增；红线 test_matching_eval 8 绿）
- 前端：`pnpm test` → **89 passed**（10 文件，subscriptionUtils 22）；`pnpm typecheck` 通过；`pnpm build` 通过（282.67 kB / gzip 84.88 kB）
- 提交范围：13 files changed, +632/-39；stat 与声明一致，无夹带

## 代码审查要点（对照验收口径）

### 符合验收
- **Additive 迁移**：`subscriptions` 的 `CREATE TABLE IF NOT EXISTS` 加入 `last_pushed_at TEXT`，并提供 `_migrate_subscriptions_add_last_pushed_at`（PRAGMA 检查列存在再 ALTER ADD COLUMN），兼容既有库。
- **推送/已读解耦**：`scan_subscriptions(engine, now, user_id=None)` 只推进 `last_pushed_at`，不改 `last_checked_at`/`new_count`；mark-read 只推进 `last_checked_at`，不改 `last_pushed_at`。checkpoint 用 `last_pushed_at or last_checked_at` 兼容旧行。
- **维护中排除**：`_enrich_subscription` 与 `scan_subscriptions` 均经 `filter_active_institution_ids`/`get_institutions_status` 过滤非维护机构，new_count/推送都不计维护中机构职位。
- **事件驱动**：crawl-run 线程 target 包成 `_crawl_then_scan`，`finally: scan_subscriptions(...)`，爬取完成后必触发扫描。
- **调度器**：`SubscriptionScheduler` daemon 线程 + `threading.Event.wait`，时钟可注入（`scan_once`/`_next_wait_seconds`/`_loop` 都用注入 clock）；挂在 FastAPI lifespan（start/stop）；配置经 `SUBSCRIPTION_SCAN_*` 读取，测试 conftest 设 `SUBSCRIPTION_SCAN_ENABLED=false` 禁用线程。
- **scan 端点**：`POST /api/subscriptions/scan` auth 依赖，按当前用户扫；每日调度器扫全部（user_id=None）。
- **前端**：`Subscription.last_pushed_at` additively 加字段；`formatLastPushed`/`subscriptionSubtitle` 改用 last_pushed_at，null→"未推送"；维护中提示变"X 家机构维护中 · 暂停推送"；api 加 `scanSubscriptions`。既有 vitest 同步更新 + 新增 1 用例。
- 未碰匹配/爬虫/导出/分析/档案/草稿链路；既有核心表结构与既有端点语义未改。

### minor（不阻塞，建议修）
1. **last_pushed_at 初始化为创建时间**：`create_subscription` 把 last_pushed_at 一并设为 now，导致新订阅卡片显示"上次推送 刚刚"、几乎不出现"未推送"态。建议新建时置 NULL（首次 scan/推送再置值），或在 `subscriptionSubtitle` 对 new_count==0 且从未 scan 的订阅显示"未推送"。
2. **调度器吞异常**：`scheduler._loop` 的 `except Exception: pass` 静默；建议至少 `logging` 一条，便于排查。
3. **crawl 触发 scan 用真实时钟**（非注入）：`test_crawl_triggers_subscription_scan` 依赖真实 fixture 爬取 + 轮询（0.5s×上限 60），属慢测试；fixture 离线、风险低，但多实例并发跑可能偶发慢。
4. **并发 SQLite 写**：调度器线程与 crawl 线程可能同时写 subscriptions，SQLite 单写者下偶有可能 `database is locked`；MVP 单实例可接受，若重视可捕获/重试。
5. **CREATE TABLE 的 SQL 缩进错乱**（subscriptions 列缩进不一致）：仅美观问题，建议恢复缩进。
6. `test_scheduler_config_values` 只断言默认 hour=9/minute=0，未测 env 覆盖值；可补。

### 主动行为变更说明（预期，非 bug）
`new_count`/`is_empty_30d` 的计算口径从「所有选中机构」改为「非维护中机构」，属本切片提示词明确要求（对齐 PRD 4.6 暂停推送）。若用户只订阅维护中机构，new_count 恒 0。既有订阅测试在 241 全绿下未破坏。

## 未 touch（核实属实）
matching/ classifier.py / crawler.py / adapters/ / exporter.py / analytics.py / resume.py / jd_structurer.py 均无改动；jobs/users/profiles/resume_drafts 表结构未改；既有端点请求/响应语义未变。