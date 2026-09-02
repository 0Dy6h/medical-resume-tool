# traework 4.1 订阅切片评审 — 2026-08-22（commit 6925e9c）

## 结论：有条件通过（无 P0/P1 阻塞）

PRD 4.1「我的订阅」MVP 切片功能正确、约束遵守、红线未动，门禁全绿。
以下 minor 项不阻塞合并，建议后续顺手修。

## 实测门禁（本沙箱实际运行，非自报）

- 后端：`uv run --project backend pytest -q` → **231 passed**（76.9s，210 基线 + 21 新增；红线 test_matching_eval 8 用例保持绿）
- 前端：`pnpm test` → **88 passed**（10 文件，其中 subscriptionUtils 21）；`pnpm typecheck` 通过；`pnpm build` 通过（282.59 kB / gzip 84.84 kB）
- 提交范围：13 files changed, +2053/-9；stat 与声明一致，未夹带无关改动

## 代码审查要点

### 符合验收口径
- 纯新增 `subscriptions` 表（user_id/name/keyword/institution_ids/last_checked_at/created_at/updated_at）+ user_id 索引；未触碰任何既有表结构/既有端点语义。
- 端点：POST(201)/GET/DELETE(204)/POST mark-read，全部走 auth 依赖；字段校验按 PRD（name 2-30、keyword 1-50、institution 1-12，默认全选 enabled 机构）。
- 用户隔离：所有 SELECT/UPDATE/DELETE 均带 `AND user_id=?`；越权/不存在统一 404（不泄露存在性）。
- 计数语义：`fetched_at > last_checked_at` + 机构 IN 过滤 + keyword LIKE（title/raw_text/institution_name）；创建时 last_checked_at=now，旧职位不计入；mark-read 推进检查点归零计数。
- 30 天空状态：`has_matching_jobs_last_30d` 以 UTC now-30d 为阈值；维护中：enabled=false 或 last_status='failed'；宽泛关键词：命中占比 >50% 时创建接口返回 warning（前端弹确认层"已创建但提示"，允许继续）。
- 时间戳格式一致（now_iso 与 jobs.fetched_at 均为 UTC ISO8601，字符串比较可靠）。
- SQL 均参数化；institution_ids 经 schema 校验为 int 列表，占位符拼接安全。
- 前端：SubscriptionsPanel + CreateSubscriptionDialog 集成 JobsPage 左侧，未登录显示"登录后使用订阅"；校验/格式化/计数/宽泛提示均抽纯函数并有 21 个单测。

### minor（不阻塞，建议修）
1. `backend/tests/test_subscriptions.py::test_disabled_institution_shows_maintenance`：`if disabled is None` 分支在 `with connect(...)` 块外使用已关闭的 `conn`（UPDATE→会抛 closed database 异常）。当前种子必有 disabled 机构，分支不触发所以测试绿；属死分支隐患，建议把 UPDATE 移入 with 块或重开连接。
2. `test_new_count_keyword_and_institution_filter`：名称与断言不符——实际只断言了 new_count==0（创建即检查点），关键词+机构过滤真实验证由 `test_new_count_jobs_after_checkpoint` 承担。建议补强断言或改名，避免未来误读。
3. `frontend/pnpm-workspace.yaml`（untracked）：本沙箱前置修复（allowBuilds: esbuild: true）仍未纳入版本库，换环境 pnpm 门禁会重新报 ERR_PNPM_IGNORED_BUILDS。建议随下次提交纳入。
4. 机构上限 12 家在后端 schema、后端默认全选 cap、前端共三处写死；当前 enabled=12 一致，未来扩容需同步。

## 未 touch（核实属实）
matching/ classifier.py / crawler.py / adapters/ / exporter.py / analytics.py / resume.py / jd_structurer.py 均无改动；既有表结构与既有端点语义未变。