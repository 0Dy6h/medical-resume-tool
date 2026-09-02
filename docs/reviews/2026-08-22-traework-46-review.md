# 评审报告 — 4.6 分析页质量闭环（解析器降级规则对齐 + 地区分布补全）

**提交**：`18dd443`（未 push）
**审核人**：项目总监（AI）
**审核日期**：2026-08-22
**结论**：✅ **Approve** — 功能正确、约束遵守、红线未动。

---

## 1. 交付与改动清单

| 文件 | 改动 | 类型 |
|---|---|---|
| `backend/app/services/analytics.py` | `_parser_quality_payload` 新增 `low_confidence_ratio` 计算并传入 `_review_status`；`_review_status` 重写为 PRD 4.6 规则 | 修改 |
| `backend/tests/test_analytics.py` | 新增 5 个单元测试 | 新增 |
| `frontend/src/pages/AnalyticsPage.tsx` | 新增「地区分布」DataBar（机构类型↔共性能力之间） | 修改 |
| `frontend/src/lib/status.ts` | `watch` 标签「观察」→「需关注」 | 修改 |
| `frontend/src/lib/status.test.ts` | 同步更新断言 | 修改 |

预期门禁：后端 206 passed（含红线 8 passed）、前端 52 passed / tsc 通过 / build 通过。

---

## 2. 独立核验（项目总监实跑）

### 2.1 后端 diff 与 PRD 4.6 一致
- 旧逻辑（过严 bug）：`low_confidence_jobs>0 → review`、`avg<0.8 → watch`。
- 新逻辑（对齐 PRD 4.6）：
  - `failed_attachment_events > 0 → review`（单快照近似「连续3天失败」，已在注释标注剔除项）
  - `avg < 0.7 或 low_confidence_ratio > 0.2 → watch`
  - 否则 `stable`
- `low_confidence_ratio = low_confidence_jobs / jobs`（jobs=0 时取 0.0，防除零）。

### 2.2 新增测试 5 项全覆盖（已实跑隔离 = 13 passed 含红线）
`test_analytics.py` 覆盖 stable / watch(低均分) / watch(高占比) / review(失败) / **low_conf_not_review（回归旧过严 bug）**，断言与新风规则逐一对应。

### 2.3 无残留旧行为断言
全仓 grep 后端测试：`test_core_flow.py:508/511` 仍断言新行为（`bjmu-notice-v1` 有失败事件→`review`、`bjmu-xlsx-v1`→`stable`），与重写后函数一致，无旧逻辑遗留测试。

### 2.4 实测门禁
- 后端全量：`uv run pytest -q` = **206 passed**（exit 0；末尾 `SAFE_DELETE` 仅沙箱临时文件清理提示，非失败）。
- 红线：`test_matching_eval` = **8 passed** 未动。
- 隔离：`test_analytics.py` + `test_matching_eval.py` = 13 passed。

### 2.5 前端源码级评审（沙箱 esbuild 禁用，无法复跑工具链）
- `AnalyticsPage.tsx`：`<DataBar title="地区分布" items={summary?.regions ?? []} />` 插入位置正确；`summary.regions` 数据来源已在 `analytics.py:35/113`（`_group_count(conn,"region",...)` + `_counter_payload`）真实产出，非空壳。
- `status.ts`：标签 `watch`→「需关注」；tone 映射 `review→danger(红)` / `watch→working(黄)` / `stable→success(绿)` 均正确，与 `StatusPill` 既有三态展示自洽；`status.test.ts` 断言已同步。
- 改动仅 5 文件，未碰 `matching/` / `crawler.py` / `profile_import/` / `exporter.py` / `jd_structurer.py` / `resume.py`。

---

## 3. 约束遵守

- ✅ **零 DB schema 变更**：`review_status` 仅为计算字段，已在 `AnalyticsSummary`/`ParserQuality` 响应模型内；`regions` 同为既有响应字段，仅补 UI。
- ✅ **红线 `test_matching_eval` = 8 passed** 未触碰；`test_jd_structurer` 的 Windows env>32767 预存 flake 已知未修（本切片无涉，本次全量也未触发）。
- ✅ 显式剔除项（快照表/时序降级、推送暂停、双子标签页）均未混入。

---

## 4. 非阻塞提示

1. 前端门禁（vitest/tsc/build）本沙箱因 esbuild 构建脚本被禁无法复跑，已源码评审替代；traework 报 52 passed / tsc 无错 / build 成功（270KB JS），合并前建议其环境再跑一次确认。
2. 本切片用单快照 `failed_attachment_events>0` 近似 PRD「连续3天失败」——属已声明的 MVP 取舍，后续若要做时序判定，需新增每日健康快照表（大特性，留待后续切片）。

---

## 5. 当前进度

领先 origin/main **6 个 commit，未 push**（用户约束不 push）：
`b170e5f` → `6edbfe2` → `42f57c6` → `21cdc2c`(4.5) → `3a69761`(4.1) → `18dd443`(4.6)。

PRD 核心切片 4.1–4.6 已全部落地（4.2 匹配、4.3 档案管理为早期既有）。下一步可评估：订阅规则+每日推送、时序降级快照表、或导出/分析后续打磨。
