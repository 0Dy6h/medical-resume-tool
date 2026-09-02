# traework 4.3 档案边界项切片评审 — 2026-08-22（commit 847a9fb）

## 结论：通过（Approve，无 P0/P1 阻塞）

重复数据检测 + 删除档案证据链引用提示，逻辑正确、约束遵守、红线未动，门禁全绿。
本切片质量高：核心逻辑抽为纯函数、边界覆盖充分、既有主流程零改动。

## 实测门禁（本沙箱实际运行）

- 后端：`uv run --project backend pytest -q` → **290 passed**（43.0s，241 基线 + 49 新增；红线 test_matching_eval 8 绿）
- 前端：`pnpm test` → **99 passed**（11 文件，profileChecks 10）；`pnpm typecheck` 通过；`pnpm build` 通过（284.65 kB / gzip 85.39 kB）
- 提交范围：8 files changed, +1030/-1；stat 与声明一致，无夹带

## 代码审查要点（对照验收口径）

### 符合验收
- **纯函数封装**：`backend/app/services/profile_checks.py` 全为无副作用函数（`parse_profile_date` / `_build_interval` / `_overlap_ratio` / `detect_time_overlap` / `check_profile_overlaps` / `count_field_references`），可单测。
- **保守日期解析**：仅识别 YYYY / YYYY-MM / YYYY-MM-DD / `至今`(now/present/current)；其余（如 `2021年6月`、残缺值）返回 None 不触发；异常年份 catch 后返回 None。不编造日期。
- **重叠判定**：`intersection / shorter` ≥ 0.5 触发；同类别（education 内、experiences 内）两两比较，跨类别不查；按 id 去重。点区间（同日）处理合理。
- **引用计数**：遍历 drafts 的 sections[].items[] / evidence[] / gaps[] 精确 `==` 匹配 profile_field_id，返回去重草稿数 + draft_ids；同草稿多处引用只计 1。
- **端点**：`POST /api/profile/check-overlap`（auth，接收 ProfilePayload，经 to_profile 后检测）；`GET /api/profile/field-references?field_id=`（auth，仅当前用户草稿作用域）。均为只读/独立端点，不改变既有 PUT/删除主流程。
- **前端**：`save()` 先 `checkOverlap` 命中 → 弹「检测到可能与已有记录重叠的经历，是否继续添加？」确认后 `doSave`；`removeItem()` 先 `checkFieldReferences` 命中 → 弹「该记录已被用于生成 X 份简历草稿，删除后相关草稿的证据链将断裂」确认后删除。取消均不执行；检测失败降级直接走原流程。
- **零 schema 变更**、不级联删草稿、仅提示不阻断、仅同类别、仅识别可靠日期——全部遵守。
- 未碰匹配引擎/爬虫/导出/分析/订阅/草稿生成逻辑。

### minor（不阻塞）
1. `_OPEN_ENDED` frozenset 里 `至今` 重复一次（无害，可清理）。
2. `check-overlap` 端点声明了 `user` 依赖但未使用（仅认证用途，可接受）。
3. 删除档案的持久化语义：确认框的「确认删除」只在**本地移除**该行，仍需用户点保存才落库（与既有交互一致，非本切片引入；PRD 的「确认后执行删除」此处指移除+后续保存）。
4. `shouldShowOverlapWarning` 对 `overlap=true` 但 `items=[]` 返回 true（该情形后端不会产生，纯函数语义无碍）。

## 未 touch（核实属实）
matching/ classifier.py / crawler.py / adapters/ / exporter.py / analytics.py / resume.py / jd_structurer.py / schedule 均无改动；既有端点请求/响应语义未变；无新增表/列。