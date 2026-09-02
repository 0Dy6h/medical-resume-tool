# traework 提示词（2026-08-22）—— 模块 4.4 简历草稿「审阅状态机 + 分步审阅页」

一次执行一项前端为主、后端轻量的增量工作，在 `D:\螃蟹's Projects\螃蟹的简历撰写工具` 本地 FastAPI+React 项目内。先读 `medical-job-prd/medical-job-prd.html` 模块 4.4（约 956–1086 行），以及现有实现：`backend/app/services/resume.py`（`generate_resume_draft` / `build_resume_sections` / `match_profile_to_job` 已产出 `sections[]`/`evidence[]`/`gaps[]`，每项带 `profile_field_id` 与 `evidence_strength`）、`backend/app/schemas.py` 的 `ResumeDraftCreate/Update/Out`、`backend/app/main.py` 的简历草稿端点（274–344）、`frontend/src/pages/ResumePage.tsx`（现有平铺编辑页，含 generate/saveDraft/exportDraft + `draft.sections.map` 渲染 + `evidence_strength` 着色）、`frontend/src/lib/api.ts` 的 draft 函数。

## 项目背景与现状评估
后端草稿生成、证据链、持久化（`POST/GET/PUT /api/resume-drafts`）、导出（`/export` docx/pdf）**已全部存在**。PRD 4.4 真正尚未实现的是「审阅」这一交互层：
- 草稿无 `status`（draft / reviewed / finalized）状态机；
- 每个 section item 无用户决策（采纳 / 修改措辞 / 删除）；
- 前端是整页平铺编辑，没有 PRD 要求的「第 X/N 项」分步进度、彩色卡片（绿=已满足 / 黄=部分满足 / 红=不满足）、证据链可视化、采纳/修改/删除按钮。

你要补的就是这一层。

## 交付 A — 后端：草稿决策字段 + 计算态 status（零 schema 变更）

约束：严禁 `ALTER TABLE`。`resume_drafts` 表结构是固定的（`sections`/`evidence`/`gaps` 均为 JSON 列），**所有新字段都塞进这些 JSON 内部**，不新增表列。

1. `ResumeDraftOut`（`backend/app/schemas.py` 约 481 行）增加 `status: str = "draft"` 字段（这是响应模型字段，非数据库列，不受零 schema 变更红线约束）。
2. section item 增加可选决策字段：`decision?: "adopt" | "edit" | "remove"`。
   - 老草稿没有该字段时，**视作 `"adopt"`**（向后兼容，已生成的草稿默认全部采纳）。
   - `decision` 存进 `sections` JSON 内的 item 对象——`PUT /api/resume-drafts/{id}` 本就整体覆盖 `sections`，无需改表，自动持久化。
3. 在 `backend/app/main.py` 的 `GET /api/resume-drafts/{draft_id}`（约 298 行）返回前，**计算并注入** `status`：
   - 遍历所有 section 的所有 item；若**全部** item 都有 `decision` 且取值 ∈ {`adopt`, `edit`, `remove`}（无缺省/pending）→ `status = "reviewed"`，否则 `status = "draft"`。
   - 本切片**不实现 `finalized` 持久态**（PRD 三态中 finalized 留待后续）；仅以 reviewed 作为「可导出」门槛。
4. 导出时排除被删除项：在 `backend/app/main.py` 的 `_draft_for_export`（约 389 行）或 `exporter.py` 渲染前，过滤掉 `decision == "remove"` 的 item。**注意**：remove 只影响导出与审阅展示，不删除档案中的真实数据（PRD 边界：修改/删除不丢失档案）。

## 交付 B — 前端：分步审阅页（在 `ResumePage.tsx` 上增量）

`frontend/src/pages/ResumePage.tsx` 已能生成/保存/导出草稿。新增「审阅模式」，不破坏现有编辑能力：

1. 状态：`reviewMode: boolean`（默认 false，保持现有编辑交互）；进入审阅后显示分步视图。
2. 进度：统计所有 section 的 item 总数 `N`，用 `currentIndex / N` 显示「第 X/N 项」（`totalItems` 来自 `draft.sections.flatMap(s => s.items).length`）。
3. 彩色卡片：每个 item 按 `evidence_strength`（来自 `evidence` 中匹配 `profile_field_id` 的项，或 item 自身的 `evidence_level`）着色：
   - `strong` / 已匹配 → 绿（已满足）
   - `partial` / `weak` → 黄（部分满足）
   - 无匹配证据 → 红（不满足 / 差距）
4. 每条 item 提供三个操作：
   - **采纳**：`decision = "adopt"`（默认即此，点选确认）。
   - **修改措辞**：该 item 的 `text` 可编辑，`decision = "edit"`（仍须保留 `profile_field_id` 关联，不虚构档案外事实）。
   - **删除**：`decision = "remove"`（仅标记，不真删；导出与审阅预览跳过）。
5. 证据链展示：对每项展示其来源——`profile_field_id` + 匹配的 `matched_terms`（来自 `draft.evidence` 中相同 `profile_field_id` 的项）。
6. 上一项 / 下一项 按钮在 items 间移动 `currentIndex`；「完成审阅」按钮将未显式决策的 item 统一视为 `adopt`，触发保存（`PUT` 带 decision 字段）并切回可导出状态。
7. `frontend/src/types.ts`：在 `ResumeSection` 的 item 类型加 `decision?: "adopt" | "edit" | "remove"`（与后端一致）。

## 硬性约束（违反即退回）
- 零数据库 schema 变更（所有新字段进 JSON 内部，不 ALTER TABLE，不新增列）。
- 不得碰 `matching/`、`adapters/`、`crawler.py`、`profile_import/`、`exporter.py` 的渲染逻辑（仅允许在 main.py 的 `_draft_for_export` 加一行 remove 过滤）、LLM `jd_structurer.py`。
- 不得编造事实；`decision="edit"` 修改后的措辞仍须关联原始 `profile_field_id`，不得引入档案中不存在的内容。
- 改动范围：后端仅 `schemas.py`（加 status 响应字段）+ `main.py`（注入 computed status + 导出过滤 remove）；前端仅 `ResumePage.tsx` + `types.ts` + 测试。不得越界。
- 现有 `backend/tests/fixtures/profile_import/` 行为不受影响。

## 交付前门禁（必须全绿）
```
cd backend && uv run --project backend pytest -q
cd ../frontend && pnpm test && pnpm typecheck && pnpm build
```
重点守护：`test_matching_eval.py` 必须 14/14 top-1、0 错源、0 误报——红线不可动。另：`test_jd_structurer.py` 在 Windows 上有超长环境变量（>32767 字符）导致的环境报错，与本任务无关，无需修复。

## 完成后
- 起服务后，POST 一份 fixture 简历 + 一个职位生成草稿，GET 该草稿确认 `status` 返回 `"draft"`；在前端点「删除」某 item 并保存，重新 GET 确认该 item `decision=="remove"` 且 `status` 仍正确；调用 `/export` 确认 remove 项不出现在导出文档中。
- 后端新增/补充测试（`backend/tests/test_resume_draft.py` 或并入现有）：① 老草稿（无 decision）GET 返回 status=draft、item 视作 adopt；② PUT 带 decision=edit/remove 后 GET 仍保留；③ 全部决策后 GET 返回 status=reviewed；④ remove 项在导出时被过滤。
- 前端测试（新增 `frontend/src/pages/resumeReview.test.ts` 或并入）：覆盖「进入审阅显示第 X/N 进度」「点删除使 item.decision=remove 且导出预览不含该 item」「完成审阅后所有 item 非 pending」。
- git commit（**不要 push**）。当前领先 origin/main 2 个 commit，本次接在其后。

项目总监会按 Spec/审核清单复审，重点看：decision 是否真持久化、computed status 是否正确、remove 不丢档案真数据、是否零 schema 变更、test_matching_eval 红线、改动是否越界。
