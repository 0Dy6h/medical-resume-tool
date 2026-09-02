# 评审报告 — traework 交付 4.1 职位情报中心增强（提交 3a69761）

> 审核人：项目总监（AI）｜日期：2026-08-22
> 对照：提示词 `2026-08-22-traework-41-match.md`（已不落文件，直接发对话）
> 提交：`3a69761`（4.1）+ `21cdc2c`（4.5 先单独成 commit）

## 结论：✅ Approve（通过）

功能正确、约束遵守、红线未动。4.5 未提交改动已随本次一并落为 `21cdc2c`，4.1 为 `3a69761`，当前领先 origin/main **5 个 commit，未 push**（符合用户约束）。

---

## 1. 后端核查（已实跑）

| 项 | 结果 |
|---|---|
| 后端全量 `pytest -q` | **201 passed**（本沙箱本次全绿，连 `test_jd_structurer` 的 Windows env flake 也未触发） |
| `tests/test_job_match.py`（4 新增） | **4 passed**：去重计数 / blocking 标志 / 无档案 match=None / 有档案 match 结构齐全 |
| 红线 `test_matching_eval.py` | **8 passed**，未动 ✅ |

### 关键逻辑核对
- **`summarize_match`**（`resume.py`）：按 `requirement` 字段去重计数，`met`=去重证据数，`total`=met+去重缺口数，`degree_percent` 四舍五入，`blocking`=任意 gap 的 `blocking`。与提示词一致 ✅
- **`attach_job_matches`**（`resume.py`）：`user_id` 为空 → `match=None`；否则 `get_profile`，若 **`profile.is_empty`** → `match=None`；否则逐 job `match_profile_to_job` → `summarize_match`。**未改动 `matching/` 内核**，仅复用既有函数 ✅
- **`jobs()` 端点**（`main.py`）：`result = list_jobs(...)` 后 `result["items"] = attach_job_matches(...)` ✅
- **`JobOut`**（`schemas.py`）：仅加 `match: dict[str, Any] | None = None` 响应字段，**零 DB schema 变更** ✅

---

## 2. 前端核查（源码级评审，沙箱 esbuild 禁跑）

| 项 | 结果 |
|---|---|
| `jobMatch.test.ts`（8 新增） | 覆盖 `computeMatchLabel`（null/undefined→none、blocking、ok 含「满足 3/5」+percent=60）+ `freshnessTag`（新/今日/3天前/fetchedAt 兜底/双空），与实现等价 ✅ |
| traework 报前端门禁 | `npx vitest run` 52 passed / `tsc -b` 无错 / `vite build` 成功 ✅ |

### 关键逻辑核对
- **`computeMatchLabel`**：`!match`→`none`；`blocking_gap`→`blocking`；否则 `ok{text,percent}`。纯函数、可测 ✅
- **`freshnessTag`**：`age≤24h`→「新」；`>24h` 且日历日差≤1→「今日」；否则 `""`；`postedAt ?? fetchedAt` 优先 postedAt ✅
- **表格渲染**：`<thead>` 增「匹配度」列（学历后、状态前）、`colSpan 6→7`；行内新鲜度徽标 + 三种匹配态（none 引导按钮跳 `/profile`、`blocking` 红标 0%、`ok` 进度条+文字）；`onClick stopPropagation` 防穿透 ✅
- **`App.tsx`**：`JobsPage` 已传 `onNavigate` ✅
- **`types.ts`**：`JobMatch` 类型 + `Job.match` 字段 ✅

---

## 3. 约束遵守

- ✅ 零数据库 schema 变更（`match` 仅 Pydantic 响应字段）
- ✅ 严禁改动 `matching/`、`crawler.py`、`profile_import/`、`exporter.py` 渲染逻辑、`jd_structurer.py`——本次仅 `resume.py` 新增 2 函数 + `schemas.py` 1 字段 + `main.py`/`JobsPage.tsx`/`types.ts`/`App.tsx`/`styles.css` + 测试（共 9 文件）
- ✅ 红线 `test_matching_eval` 8 passed 未动

---

## 4. 非阻塞提示（不影响通过）

1. **门禁口径**：traework 报 `200 passed + 1 flake`（`test_crawl_deduplicates_by_source_text_hash...` 竞态，隔离通过），但本沙箱本次 `201 passed` 全绿、未触发该 flake——属竞态/环境相关，**非 4.1 引入**。建议 traework 在其环境偶发复跑确认竞态确为隔离通过。
2. **前端工具链**：本沙箱 esbuild 构建脚本被禁无法复跑，已源码评审替代（8 测试与实现等价）。合并前建议在其环境再跑一次 `pnpm test/typecheck/build` 确认。

---

## 5. 设计决策核对

- 无档案检测用 `profile.is_empty`（`get_profile` 返空 Profile 而非抛 KeyError）——与设计一致 ✅
- `requirement` 去重（一条要求命中多条事实仍计 1 met）✅
- `freshnessTag` 规则（新/今日/空）✅
- 零 schema 变更 ✅

---

下一步可从 PRD **4.6 分析**（差距可视化可复用本 match/appendix 数据）择机切片。
