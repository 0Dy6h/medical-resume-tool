# traework 第四轮两切片评审 — 2026-08-23（09ae88c → 57259a2）

## 结论：通过（Approve，无 P0/P1）——上轮 4 条 P2 全部闭环

本轮最大风险点是「为 9 个无注释的未适配机构编造技术原因」。逐字核对后确认未发生：真实性红线守住。

## 实测门禁（本沙箱实际运行）

- 后端：`uv run --project backend pytest -q` → **305 passed**（45.7s；红线 test_matching_eval 全绿）
- 前端：`pnpm test` → **143 passed**（14 文件）；`pnpm typecheck` clean；`pnpm build` 通过（291.97 kB / gzip 87.51 kB）

## 切片 1 — 上轮 P2 清理（09ae88c）

| P2 | 处理 |
|---|---|
| 重新导入后「已归类」残留（真 bug） | `handleImportFile` 开头 `setAssignedBlocks({})` + `setBlockAssignSelections({})`，已闭环；补 3 条重置语义断言 |
| 标签集合名取自 select 当前值 | `assignedBlocks` 由 `Set<string>` 改为 `Record<string, string>`（blockKey → collection），标签读 `assignedBlocks[blockKey]`，语义显式 |
| logger 夹在 import 之间 | 已移至全部 import 之后 |
| 两处 ~35 行 JSX 重复 | 抽出 `UnassignedBlockRow` 组件，两处复用，行为样式不变 |

## 切片 2 — 机构适配状态一等公民化（57259a2）

### 真实性核验（本轮重点，逐条比对）

- 9 条有注释的原因**逐字搬运**，无改写润色：id 8「SPA 渲染，需 headless browser」、12「需要进一步分析页面结构」、13/20/26「站点连接超时」、15「招聘系统 404」、16「列表页可达但内容需进一步适配」、23「招聘页需要登录」、30「招聘频道混合采购公告，需专用解析器」——与 seeds.py 原注释一致。
- 9 条无注释的（id 9/10/14/17/18/22/24/25/29）统一使用「尚未适配该站点，暂未启用」，**未臆造任何技术原因**。
- id 映射正确（seed 每条 10 行，注释行号 ÷10 = id），与源文件核对无误。
- **无任何机构被从 enabled=False 改成 True**：seeds.py diff 为纯追加，未触碰任何 seed 条目——没有靠改开关制造"覆盖率提升"。
- 测试④断言 `disabled_ids == BLOCKED_REASONS.keys()`，漏填/多填都会红，防止后续 seed 增减时静默失配。

### 实现

- `BLOCKED_REASONS: dict[int, str]` 置于 seeds.py 模块级，未给 SEED_INSTITUTIONS 加键、未动 database.py 的 INSERT——零 schema 变更、零迁移，绑定路径无风险。
- `InstitutionOut.blocked_reason: str | None = None` 纯增量；机构列表端点按 enabled 补 None 或原因（带 default 兜底）。
- 抓取守卫：全未适配 → 400 且 detail 逐字「所选机构均尚未适配，无法抓取」；部分未适配 → 只抓已适配，`logger.info` 记录跳过的 id/name/reason；`create_crawl_run` 与 `execute_crawl_run` 均只收已适配机构——**修掉了此前"页面全选会真去抓已知不可用站点"的问题**。
- CrawlPage：`未适配` tag、原因文字入状态列、复选框禁用且 title 为原因、全选/仅已启用均排除未适配、表头「机构覆盖：X/Y 已适配」从数据实时计算（无硬编码）。
- 纯函数 `adaptationCoverage` / `allAdaptedIds` 抽出并导出，8 条前端测试覆盖空/全适配/混合/全未适配。
- AGENTS.md 相应描述已更新为「blocked reasons 结构化于 seeds.BLOCKED_REASONS，经 /api/institutions 暴露」，未顺手改写其他内容。

## minor（不阻塞）

1. `selectAll` 与 `selectEnabled` 现在实现完全相同（都是 `allAdaptedIds`），「全选」与「仅已启用」两个按钮行为一致——建议下轮合并为一个按钮，或让「全选」保留"选中全部可选项"语义并另设文案区分。
2. 未适配机构的状态列改为只显示原因，`last_status` / `last_error` 被隐藏。当前未适配机构不会被抓取因而无历史状态，实际无损；若将来某机构被停用但有历史状态，会看不到。
3. 端点内使用函数内 `from app.services.seeds import BLOCKED_REASONS`（与既有 `from app.config import config` 风格一致，可接受）；模块级 import 更整洁。

## 未 touch（核实属实）

matching/、adapters/、crawler.py、jd_structurer.py、backend profile_import/、exporter.py 零触碰；institutions 表结构与 INSERT 未动；无新增依赖；无内联 style。

## 当前状态

PRD 4.1–4.6 边界条目全部实现；机构适配状态已数据化并在界面透明呈现（12/30 已适配，18 条原因可见）。后续唯一实质缺口是新增站点适配器（需真实 fixture）与附件 PDF 解析（AGENTS.md 要求带 fixtures 与测试）。
