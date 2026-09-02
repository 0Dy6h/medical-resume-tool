# 给 traework 的执行提示词 — PRD 模块 4.5 导出增强（诊断附录 + 导出护栏）

> 你是 traework。请按以下规格实现 PRD 4.5「导出与投递准备」的剩余缺口。项目总监（AI 审核）会对照本文件逐条验收。

## 0. 背景与现状（必读，避免重复造轮子）

- 已完成 4.4：草稿每个 item 有 `decision: adopt|edit|remove`，后端 `_compute_draft_status(draft)` 在 POST/GET/PUT 返回注入 `status`（全 item 有 decision→`reviewed`，否则 `draft`）；`_draft_for_export(draft, mode)` 在 application 与 diagnostic 两种模式都过滤 `decision=="remove"`，且 application 模式额外剔除 `gaps` 段落（id=`gaps` 或 title=`投递前需补充确认`）。
- 现状导出器 `backend/app/services/exporter.py` 的 `export_docx` / `export_pdf` **只渲染** 姓名+联系方式头 + 各 section 标题与项目符号。**没有**诊断版差距附录，**没有**任何护栏。
- 草稿 `draft` 字典已含 `evidence`（list，每项 `{requirement, profile_field_id, collection, matched_terms, source_text, source_label, score, evidence_strength}`）与 `gaps`（list，每项 `{requirement, message, ...}`）。数据全在，无需改动任何上游。
- 前端导出入口：`frontend/src/pages/ResumePage.tsx` 的 `exportDraft(format, mode)`，经 `frontend/src/lib/api.ts` 的 `exportResume(draftId, format, mode)` 调用 `POST /api/resume-drafts/{id}/export?format=&mode=`。当前已有「投递 DOCX / 投递 PDF / 诊断 DOCX」三个按钮。

## 1. 目标

实现 PRD 4.5 的两条核心能力，且**零数据库 schema 变更**：

1. **诊断版差距附录**：`mode="diagnostic"` 导出时，在简历正文之后追加结构化的「匹配分析附录」，逐条列出硬性要求及其满足状态、对应档案证据、未满足项的准备建议。
2. **导出护栏**：未审阅完成（status=draft，仍有未决策项）与空内容（全部可导出项被删除）两种边界，按 PRD 拦截并给出可继续的提示。

## 2. 任务 A — 后端：诊断附录渲染（改 exporter.py）

在 `exporter.py` 中：

- 给 `export_docx(draft, include_appendix: bool = False)` 与 `export_pdf(draft, include_appendix: bool = False)` 各追加 `include_appendix` 参数（默认 False，保持现有调用兼容）。
- 当 `include_appendix=True` 时：
  1. 渲染正文时**跳过** `id=="gaps"` 的段落（避免与附录里的差距项重复；application 模式本就已在 `_draft_for_export` 剔除，故仅 diagnostic 受影响）。
  2. 正文之后追加附录，结构如下（docx 用 `add_heading`/`add_paragraph`，pdf 用 `multi_cell`，逐项缩进）：
     - 标题：`匹配分析附录`
     - 子标题：`已满足的硬性要求`，遍历 `draft["evidence"]`，每条：
       - 行：`✅ {requirement}`
       - 证据行（缩进）：`证据：{source_text}` + 若有 `matched_terms` 则补 `（匹配关键词：{term1}、{term2}）`
     - 子标题：`需补充确认的差距项`，遍历 `draft["gaps"]`，每条：
       - 行：`⚠️ {requirement}`
       - 建议行（缩进）：`建议：{message}`
- 附录内容必须**确定性强、可断言**：固定中文字符串 `匹配分析附录`、`已满足的硬性要求`、`需补充确认的差距项`、`✅`、`⚠️` 必须出现在导出的 docx XML / pdf 文本中；某条 `requirement` 文本也要出现。
- 不得改变 application 模式（include_appendix=False）的既有输出结构与样式。

## 3. 任务 B — 后端：导出护栏（改 main.py 导出端点）

修改 `backend/app/main.py` 的 `export_resume`（约 325 行）：

- 新增 query 参数 `override: Annotated[bool, Query()] = False`。
- 在取到 `draft` 后、调用 `_draft_for_export` 之前，计算：
  - `pending =` 所有 section 的 item 中 `decision` 不在 `{adopt,edit,remove}` 的数量（复用与 `_compute_draft_status` 相同的判定）。
  - 若 `pending > 0` 且 `override is False` → 返回 `409`，JSON body：`{"detail": f"您还有{pending}项内容未审阅，建议完成审阅后再导出", "pending": pending, "allow_override": True}`。
- 在 `_draft_for_export(draft, mode)` 之后，计算可导出正文项：剔除 `id=="gaps"` 段落后的所有 item（即去掉 gaps 段落，因为该段落只是提示，不应算"简历内容"）。若数量为 0 → 返回 `422`，JSON body：`{"detail": "当前简历内容为空，请返回审阅页面至少采纳一项内容"}`。
  - 注意：空内容拦截**不受 override 影响**（override 只跳过"未审阅"拦截，不跳过"空内容"拦截）。
- 渲染时，依据 `mode == "diagnostic"` 给 `export_docx` / `export_pdf` 传入 `include_appendix=True`，否则 `False`。
- 保持 `format` 仅支持 `docx|pdf`（不新增 diagnostic 第三种 format，避免与现有前端/端点签名冲突；PRD 中"诊断版"以 `mode=diagnostic` 表达即可）。
- 端点其余行为（404 草稿不存在、Content-Disposition 文件名、media_type）保持不变。

## 4. 任务 C — 前端：护栏交互（改 ResumePage.tsx + api.ts）

### 4.1 lib/api.ts
- `exportResume(draftId, format, mode="application", override=false)`：在 URL 上追加 `&override=true`（仅当 override 为 true）。
- 确保非 2xx 响应会 `throw new Error(body.detail || "导出失败")`（若当前实现已抛错则保持不变；若未抛，请补上，使 409/422 的 `detail` 能上抛到 UI）。

### 4.2 ResumePage.tsx
- 导出**前**先做前端轻量校验（避免无谓请求）：提取一个**纯函数**并导出供测试 `exportBlock(draft: ResumeDraft): { pending: number; empty: boolean }`：
  - `pending` = 所有 section item 中 `decision` 不在 `{adopt,edit,remove}` 的数量（与后端判定一致）。
  - `empty` = 剔除 `id=="gaps"` 段落后，剩余 item 数量为 0。
- `exportDraft` 流程改为：
  1. 若 `empty` → `toast.error("当前简历内容为空，请返回审阅页面至少采纳一项内容")`，中止。
  2. 若 `pending > 0` 且用户尚未确认 override → 弹出**确认对话框**（不要用浏览器原生 confirm；用页面内 state 控制的一个小弹层/confirm 区域，含两按钮）：
     - 「继续导出（未审阅项默认不纳入）」→ 以 `override=true` 重新调用 `api.exportResume`，成功后下载并 toast。
     - 「返回审阅」→ 关闭弹层、进入审阅模式（`enterReview()`）。
  3. 否则直接 `api.exportResume(..., override)` 并下载。
- 现有三个导出按钮（投递 DOCX / 投递 PDF / 诊断 DOCX）行为不变，仅内部走新的 `exportDraft` 护栏逻辑；诊断按钮仍传 `mode="diagnostic"`。

### 4.3 前端测试
新增 `frontend/src/pages/exportGuard.test.ts`，至少覆盖：
- `exportBlock`：全决策 → pending=0, empty=false；部分决策 → pending>0；全部 remove → empty=true。
- 覆盖 `computeDraftStatus`（已存在）与 `exportBlock` 对 `decision` 判定的**一致性**（同一份 sections 两者结论应吻合）。

## 5. 硬性约束（违反即打回）

- **零数据库 schema 变更**。`decision`/`status` 已存于 `sections`/`evidence` JSON 内，禁止新增任何表/列/迁移。
- **禁止改动**：`backend/app/services/matching/`、`adapters/`、`crawler.py`、`profile_import/`、`classifier.py`、JD 结构化（`jd_structurer` 相关）。本次只动 `exporter.py` + `main.py` 导出端点 + 前端导出相关文件 + 测试。
- **红线**：`backend/tests/test_matching_eval.py` 必须 **8 passed**（与 4.4 一致）。这是不可触碰的生命线。
- `test_jd_structurer.py` 在 Windows 上有 env var >32767 字符的**预存 flake**，与本任务无关，**不要尝试修复它**，也不要让它计入你的门禁结论。
- 诊断附录的文案为固定中文字符串，必须可被测试断言（见任务 A）。

## 6. 验收标准（EARS，总监据此验收）

- WHEN 用户以 `mode=diagnostic` 导出 THEN 文档末尾含「匹配分析附录」，逐条列出 evidence（标记✅满足+证据/关键词）与 gaps（标记⚠️未满足+建议），且正文不含独立的「投递前需补充确认」段落。
- WHEN 用户以 `mode=application` 导出 THEN 文档**不含**「匹配分析附录」。
- WHEN 导出草稿存在未审阅项（status=draft）且未 override THEN 端点返回 409，body 含 `pending` 数量与 `allow_override=true`。
- WHEN 前端收到 409 且用户选择继续 THEN 以 `override=true` 重新请求并成功导出，未审阅项不纳入正文。
- WHEN 草稿所有可导出项均被删除（remove）THEN 端点返回 422，提示内容为空；此拦截不受 override 影响。
- WHEN 任意导出 THEN PDF/DOCX 文件正常生成、可下载，既有 application 渲染样式不退化。

## 7. 门禁（提交前必须全绿）

后端（在 `backend/` 下 `uv run pytest -q`）：
- `test_matching_eval`：8 passed（红线）
- 新增/扩展测试覆盖：diagnostic 附录内容断言、application 无附录、未审阅 409+pending、override 绕过、空内容 422。
- 其余测试通过（忽略预存的 `test_jd_structurer` Windows flake）。

前端（在 `frontend/` 下）：
- `pnpm test`（vitest）：新增 `exportGuard.test.ts` 全绿，原有测试不回归。
- `pnpm typecheck` 通过。
- `pnpm build` 通过。

## 8. 交付要求

- 提交信息格式：`feat(export): 诊断版差距附录 + 未审阅/空内容导出护栏`。
- **保持未 push**（当前已领先 origin/main 3 个 commit），提交后报告门禁结果，由总监审核。
- 报告需列出：改动文件清单、新增/修改测试、门禁结果（明确区分真实通过与预存 flake）、是否零 schema 变更、是否触碰红线相关文件。
