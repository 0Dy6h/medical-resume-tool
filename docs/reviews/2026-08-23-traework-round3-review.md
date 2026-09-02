# traework 第三轮两切片评审 — 2026-08-23（133abe7 → e65be4c）

## 结论：通过（Approve，无 P0/P1）——附 1 条 P2 建议下轮修

PRD 4.3「未归类原文手动归类」与 PRD 4.5「文件生成失败」两条边界均按提示词落地，实现路径与真实性约束遵守到位。

## 实测门禁（本沙箱实际运行）

- 后端：`uv run --project backend pytest -q` → **299 passed**（45.3s；红线 test_matching_eval 全绿）
- 前端：`pnpm test` → **132 passed**（13 文件）；`pnpm typecheck` clean；`pnpm build` 通过（291.60 kB / gzip 87.19 kB）
- 变更范围：5 文件（main.py、test_core_flow.py、ProfilePage.tsx、profileImport.test.ts、styles.css），与声明一致

## 切片 1 — 未归类原文手动归类（133abe7）

- `buildManualAssignment`：configByKey 查配置、未知集合返回 null、主字段取 `fields[0].key`、`text.trim()` 逐字搬运、area 字段初始化 `[]`、函数内不生成 id——与提示词逐条一致。
- 真实性红线遵守：只搬运原文，不改写、不补全、不推断其他字段；未归类原文列表内容未被修改或删除（仅外层包了 `.unassigned-text`）。
- 实现路径正确：走「预填档案表单」，`assignBlockToCollection` 只改本地 profile state，落库仍由用户点保存走既有 PUT 流程；importMerge.ts 与预览勾选合并逻辑零触碰。
- 两处「未归类原文」（导入提示面板 + 导入预览面板）都接了 select + 归类按钮，blockKey 分别用 `empty-` / `preview-` 前缀，跨面板不串键。
- 展开目标集合复用既有 collapsedSections；滚动定位用 `sectionRefs` 回调 ref 挂在每个集合 section 上，确认已接。
- 样式走 styles.css 新增三个类并复用 `var(--muted)`，无内联 style。
- 测试 13 条：九个集合主字段映射逐条断言 + trim 语义 + 未知集合 null + area 字段初始化 + 「函数内不生成 id」。

## 切片 2 — 导出失败兜底与后台日志（e65be4c）

- `export_docx` / `export_pdf` 各自包 try/except Exception；`logger.exception` 保留堆栈，日志格式含 draft_id 与 format。
- 对外 500 + 文案逐字「文件生成失败，请稍后重试」；`raise ... from None` 避免向客户端泄漏链式异常。
- 关键约束守住：409 未审阅、422 空内容守卫位于 try 之外，不会被兜底吞成 500，且有两条专门的回归测试断言。
- 测试 4 条：docx/pdf 异常路径各断言 500 + 逐字文案 + caplog ERROR 记录（含 draft_id、format、异常消息、堆栈），外加 409/422 回归。
- 前端未改：ResumePage 导出失败已 toast error.message，PRD 文案自动透出——核实属实。

## P2（不阻塞，建议下轮顺手修）

1. **重新导入后「已归类」标记残留**：`assignedBlocks` / `blockAssignSelections` 在 `handleImportFile` 里没有重置。若用户再次导入同一份文件（或另一份文件的同位置文本完全相同），该行会直接显示「已归类到 XXX」且归类按钮消失，导致本次无法归类——本地状态与实际档案内容脱节。修法一行：`handleImportFile` 开头 `setAssignedBlocks(new Set()); setBlockAssignSelections({});`。
2. 「已归类到 XXX」标签的集合名取自 `blockAssignSelections[blockKey]` 而非记录实际归类的集合。当前 select 归类后即卸载、值不可能再变，因此行为正确；但显式记录归类目标（如 `Map<blockKey, collection>`）更抗未来重构。
3. `main.py` 的 `logger = logging.getLogger(__name__)` 夹在标准库 import 与 fastapi import 之间，PEP8/E402 视角略怪，建议移到全部 import 之后。
4. 两处未归类原文行的 JSX（约 35 行）完全重复，可抽成一个小组件；当前重复量可接受。

## 未 touch（核实属实）

matching/、adapters/、crawler.py、jd_structurer.py、backend profile_import/、exporter.py 零触碰；零 DB schema 变更；无新增依赖；无内联 style。

## PRD 边界完成度

至此 PRD 4.1–4.6 的边界与异常条目已全部实现。后续可选方向：机构覆盖扩展（30 个种子仅 6 个适配器，需 fixtures + 测试或显式 blocked reason）、附件 PDF 解析（AGENTS.md 明确要求带 fixtures 与测试才动）。
